from __future__ import annotations

import argparse
import json
from pathlib import Path

from hermes_forge import __version__
from hermes_forge.analysis import analyze_evidence
from hermes_forge.collectors.cron import collect_cron_evidence
from hermes_forge.collectors.logs import collect_log_evidence
from hermes_forge.collectors.profiles import discover_profiles
from hermes_forge.collectors.skills import collect_skill_evidence
from hermes_forge.models import EvidenceItem, Finding
from hermes_forge.paths import is_under, resolve_hermes_home, write_text_under
from hermes_forge.proposals import render_proposals
from hermes_forge.redaction import redact_json, safe_path_label


def _load_ledger(path: Path) -> list[EvidenceItem]:
    items = []
    if not path.exists():
        return items
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        items.append(EvidenceItem(**data))
    return items


def cmd_scan(args: argparse.Namespace) -> int:
    home = resolve_hermes_home(args.hermes_home)
    out = Path(args.out).resolve()
    if is_under(out, home):
        print(json.dumps({"ok": False, "status": "OUT_UNDER_HERMES_HOME_BLOCKED", "reason": "Forge scan writes only to an output directory outside the Hermes input home."}, indent=2))
        return 2
    out.mkdir(parents=True, exist_ok=True)
    inventory = discover_profiles(home, all_profiles=args.all_profiles, profile=args.profile)
    evidence = []
    next_id = 1
    for row in inventory["profiles"]:
        if not row.get("exists") or row.get("status") == "skipped_symlink":
            continue
        profile_name = row["name"]
        profile_path = home if profile_name == "default" else home / "profiles" / profile_name
        for collector in [
            lambda p, n: collect_skill_evidence(p, n, home, next_id),
            lambda p, n: collect_cron_evidence(p, n, home, next_id),
            lambda p, n: collect_log_evidence(p, n, next_id),
        ]:
            batch = collector(profile_path, profile_name)
            evidence.extend(batch)
            next_id += len(batch)
    write_text_under(out / "inventory.json", out, json.dumps(redact_json(inventory), ensure_ascii=False, indent=2))
    ledger = "\n".join(json.dumps(redact_json(e.to_dict()), ensure_ascii=False) for e in evidence) + ("\n" if evidence else "")
    write_text_under(out / "evidence-ledger.jsonl", out, ledger)
    write_text_under(out / "source-ledger.md", out, f"# Source ledger\n\n- hermes_home: {inventory['hermes_home']}\n- profiles: {len(inventory['profiles'])}\n- evidence_items: {len(evidence)}\n")
    summary = {"schema_version": "hermes-forge.scan-summary/v1", "profiles": len(inventory["profiles"]), "evidence_items": len(evidence), "apply_enabled": False}
    write_text_under(out / "scan-summary.json", out, json.dumps(summary, ensure_ascii=False, indent=2))
    write_text_under(out / "redaction-report.json", out, json.dumps({"schema_version": "hermes-forge.redaction-report/v1", "redaction_enabled": True}, indent=2))
    print(json.dumps({"ok": True, "status": "OK", "out": safe_path_label(out, home), "summary": summary}, ensure_ascii=False, indent=2))
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    scan = Path(args.scan).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    items = _load_ledger(scan / "evidence-ledger.jsonl")
    findings = analyze_evidence(items)
    payload = {"schema_version": "hermes-forge.findings/v1", "findings": [f.to_dict() for f in findings]}
    write_text_under(out / "findings.json", out, json.dumps(redact_json(payload), ensure_ascii=False, indent=2))
    md = ["# Forge findings", ""]
    if not findings:
        md.append("- No findings. NO_CHANGE is recommended.")
    for f in findings:
        md.append(f"## {f.id} / {f.type}")
        md.append(f"- severity: `{f.severity}`")
        md.append(f"- evidence: `{', '.join(f.evidence_ids)}`")
        md.append(f"- next_action: {f.next_action}")
        md.append("")
    write_text_under(out / "findings.md", out, "\n".join(md) + "\n")
    write_text_under(out / "dedup-groups.json", out, json.dumps({"schema_version": "hermes-forge.dedup/v1", "groups": []}, indent=2))
    print(json.dumps({"ok": True, "status": "OK", "findings": len(findings), "out": safe_path_label(out)}, indent=2))
    return 0


def cmd_propose(args: argparse.Namespace) -> int:
    analysis = Path(args.analysis).resolve()
    data = json.loads((analysis / "findings.json").read_text(encoding="utf-8"))
    findings = [Finding(**f) for f in data.get("findings", [])]
    out = Path(args.out).resolve()
    written = render_proposals(findings, out)
    print(json.dumps({"ok": True, "status": "OK", "proposals": len(written), "out": safe_path_label(out)}, indent=2))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    proposal = Path(args.proposal).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    data = json.loads(proposal.read_text(encoding="utf-8"))
    plan = {"schema_version": "hermes-forge.eval-plan/v1", "proposal_id": data.get("id"), "checks": ["schema", "privacy", "no-live-apply"], "status": "PLAN_ONLY"}
    write_text_under(out / "eval-plan.json", out, json.dumps(plan, indent=2))
    write_text_under(out / "deterministic-checks.json", out, json.dumps({"schema_version": "hermes-forge.deterministic-checks/v1", "checks": plan["checks"]}, indent=2))
    print(json.dumps({"ok": True, "status": "OK", "out": safe_path_label(out)}, indent=2))
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    print(json.dumps({"ok": False, "status": "APPLY_DISABLED_IN_MVP", "proposal": safe_path_label(args.proposal), "reason": "Forge MVP does not mutate live Hermes files."}, indent=2))
    return 2


def cmd_rollback(args: argparse.Namespace) -> int:
    print(json.dumps({"ok": True, "status": "NO_APPLY_LOG", "apply_id": args.apply_id, "reason": "No changes are applied in MVP."}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hermes Forge: local-first improvement control plane for Hermes Agent")
    parser.add_argument("--version", action="version", version=f"hermes-forge {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)
    scan = sub.add_parser("scan")
    scan.add_argument("--hermes-home")
    group = scan.add_mutually_exclusive_group()
    group.add_argument("--profile")
    group.add_argument("--all-profiles", action="store_true")
    scan.add_argument("--out", required=True)
    scan.set_defaults(func=cmd_scan)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("--scan", required=True)
    analyze.add_argument("--out", required=True)
    analyze.set_defaults(func=cmd_analyze)
    propose = sub.add_parser("propose")
    propose.add_argument("--analysis", required=True)
    propose.add_argument("--out", required=True)
    propose.set_defaults(func=cmd_propose)
    ev = sub.add_parser("eval")
    ev.add_argument("--proposal", required=True)
    ev.add_argument("--out", required=True)
    ev.set_defaults(func=cmd_eval)
    apply = sub.add_parser("apply")
    apply.add_argument("--proposal", required=True)
    apply.set_defaults(func=cmd_apply)
    rollback = sub.add_parser("rollback")
    rollback.add_argument("apply_id")
    rollback.set_defaults(func=cmd_rollback)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
