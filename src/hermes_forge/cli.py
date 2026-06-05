from __future__ import annotations

import argparse
import json
from pathlib import Path

from hermes_forge import __version__
from hermes_forge.capabilities import build_capabilities, dumps, run_doctor
from hermes_forge.analysis import analyze_evidence
from hermes_forge.collectors.cron import collect_cron_evidence
from hermes_forge.collectors.doctor import collect_doctor_report_evidence
from hermes_forge.collectors.kanban import collect_kanban_evidence
from hermes_forge.collectors.logs import collect_log_evidence
from hermes_forge.collectors.profiles import discover_profiles
from hermes_forge.collectors.sessions import collect_session_evidence
from hermes_forge.collectors.skills import collect_skill_evidence
from hermes_forge.diff_preview import run_diff_preview
from hermes_forge.experiment import run_experiment
from hermes_forge.improve import run_improve
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


def _bump_next_id(next_id: int, evidence: list[EvidenceItem], batch: list[EvidenceItem]) -> int:
    evidence.extend(batch)
    return next_id + len(batch)


def cmd_capabilities(args: argparse.Namespace) -> int:
    print(dumps(build_capabilities()))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    print(dumps(run_doctor()))
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    home = resolve_hermes_home(args.hermes_home)
    out = Path(args.out).resolve()
    if is_under(out, home):
        print(json.dumps({"ok": False, "status": "OUT_UNDER_HERMES_HOME_BLOCKED", "reason": "Forge scan writes only to an output directory outside the Hermes input home."}, indent=2))
        return 2
    out.mkdir(parents=True, exist_ok=True)
    inventory = discover_profiles(home, all_profiles=args.all_profiles, profile=args.profile)
    evidence: list[EvidenceItem] = []
    next_id = 1
    adapters: dict[str, dict[str, object]] = {
        "profiles": {"status": "enabled"},
        "skills": {"status": "enabled"},
        "cron": {"status": "enabled"},
        "logs": {"status": "enabled"},
        "sessions": {"status": "enabled", "mode": "metadata_only"},
        "kanban": {"status": "enabled" if args.kanban_db else "not_configured", "mode": "metadata_only"},
        "doctor_report": {"status": "enabled" if args.doctor_report else "not_configured", "mode": "safe_summary_only"},
    }
    for row in inventory["profiles"]:
        if not row.get("exists") or row.get("status") == "skipped_symlink":
            continue
        profile_name = row["name"]
        profile_path = home if profile_name == "default" else home / "profiles" / profile_name
        for collector in [
            lambda p, n, i: collect_skill_evidence(p, n, home, i),
            lambda p, n, i: collect_cron_evidence(p, n, home, i),
            lambda p, n, i: collect_log_evidence(p, n, i),
            lambda p, n, i: collect_session_evidence(p, n, home, i),
        ]:
            batch = collector(profile_path, profile_name, next_id)
            next_id = _bump_next_id(next_id, evidence, batch)
    next_id = _bump_next_id(next_id, evidence, collect_kanban_evidence(Path(args.kanban_db) if args.kanban_db else None, home, next_id))
    next_id = _bump_next_id(next_id, evidence, collect_doctor_report_evidence(Path(args.doctor_report) if args.doctor_report else None, home, next_id))
    inventory["adapters"] = adapters
    write_text_under(out / "inventory.json", out, json.dumps(redact_json(inventory), ensure_ascii=False, indent=2))
    ledger = "\n".join(json.dumps(redact_json(e.to_dict()), ensure_ascii=False) for e in evidence) + ("\n" if evidence else "")
    write_text_under(out / "evidence-ledger.jsonl", out, ledger)
    by_source: dict[str, int] = {}
    for item in evidence:
        by_source[item.source_type] = by_source.get(item.source_type, 0) + 1
    source_lines = ["# Source ledger", "", f"- hermes_home: {inventory['hermes_home']}", f"- profiles: {len(inventory['profiles'])}", f"- evidence_items: {len(evidence)}", "", "## Adapter status"]
    for name, status in sorted(adapters.items()):
        source_lines.append(f"- {name}: {status['status']}")
    write_text_under(out / "source-ledger.md", out, "\n".join(source_lines) + "\n")
    summary = {"schema_version": "hermes-forge.scan-summary/v1", "profiles": len(inventory["profiles"]), "evidence_items": len(evidence), "evidence_by_source": by_source, "adapters": adapters, "apply_enabled": False}
    write_text_under(out / "scan-summary.json", out, json.dumps(redact_json(summary), ensure_ascii=False, indent=2))
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
        md.append("- No findings. NO_CHANGE proposal is recommended.")
    for f in findings:
        md.append(f"## {f.id} / {f.type}")
        md.append(f"- priority: `{f.priority_label}` / `{f.priority_score}`")
        md.append(f"- severity: `{f.severity}`")
        md.append(f"- evidence: `{', '.join(f.evidence_ids)}`")
        md.append(f"- review_focus: {f.review_focus}")
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
    target_type = data.get("target_type", "unknown")
    checks = ["schema", "privacy", "no-live-apply", "rollback-plan"]
    if target_type == "no_change":
        checks.extend(["evidence-insufficient", "no-change-rationale"])
    else:
        checks.extend(["evidence-linked", "diff-preview-only", "manual-review-required"])
    plan = {"schema_version": "hermes-forge.eval-plan/v1", "proposal_id": data.get("id"), "target_type": target_type, "checks": checks, "status": "PLAN_ONLY", "semantic_judge_enabled": False}
    write_text_under(out / "eval-plan.json", out, json.dumps(redact_json(plan), indent=2))
    write_text_under(out / "deterministic-checks.json", out, json.dumps({"schema_version": "hermes-forge.deterministic-checks/v1", "checks": checks, "stable_order": True}, indent=2))
    print(json.dumps({"ok": True, "status": "OK", "out": safe_path_label(out)}, indent=2))
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    print(json.dumps({"ok": False, "status": "APPLY_DISABLED_IN_MVP", "proposal": safe_path_label(args.proposal), "reason": "Forge MVP does not mutate live Hermes files."}, indent=2))
    return 2


def cmd_rollback(args: argparse.Namespace) -> int:
    print(json.dumps({"ok": True, "status": "NO_APPLY_LOG", "apply_id": args.apply_id, "reason": "No changes are applied in MVP."}, indent=2))
    return 0


def cmd_diff_preview(args: argparse.Namespace) -> int:
    result = run_diff_preview(
        experiment=args.experiment,
        out=args.out,
        hermes_home=args.hermes_home,
    )
    print(json.dumps(redact_json(result), ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


def cmd_experiment(args: argparse.Namespace) -> int:
    result = run_experiment(
        opportunity_source=args.opportunity,
        opportunity_id=args.id,
        out=args.out,
        run=args.run,
    )
    print(json.dumps(redact_json(result), ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


def cmd_improve(args: argparse.Namespace) -> int:
    result = run_improve(
        hermes_home=args.hermes_home,
        out=args.out,
        profile=args.profile,
        all_profiles=args.all_profiles,
        kanban_db=args.kanban_db,
        doctor_report=args.doctor_report,
        baseline=args.baseline,
        top=args.top,
        mode=args.mode,
    )
    print(json.dumps(redact_json(result), ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hermes Forge: local-first improvement control plane for Hermes Agent")
    parser.add_argument("--version", action="version", version=f"hermes-forge {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)
    doctor = sub.add_parser("doctor", help="Run Forge self-check. Does not inspect or mutate a live Hermes home.")
    doctor.set_defaults(func=cmd_doctor)
    capabilities = sub.add_parser("capabilities", help="Print machine-readable Forge capability and side-effect report.")
    capabilities.set_defaults(func=cmd_capabilities)
    improve = sub.add_parser("improve", help="Run a universal read-only improvement loop and write a human report plus safe artifacts.")
    improve.add_argument("--mode", default="read-only", choices=["read-only"], help="Improvement loop mode. Only read-only is supported in the current safety boundary.")
    improve.add_argument("--hermes-home")
    improve_group = improve.add_mutually_exclusive_group()
    improve_group.add_argument("--profile")
    improve_group.add_argument("--all-profiles", action="store_true")
    improve.add_argument("--kanban-db", help="Optional Kanban SQLite DB to import as aggregate metadata only.")
    improve.add_argument("--doctor-report", help="Optional existing Hermes/System Doctor report to import as a safe summary only.")
    improve.add_argument("--baseline", help="Optional previous improve output directory or scan-summary.json for safe delta comparison.")
    improve.add_argument("--top", type=int, default=7, help="Maximum number of opportunities to render in report.md.")
    improve.add_argument("--out", required=True)
    improve.set_defaults(func=cmd_improve)
    experiment = sub.add_parser("experiment", help="Create a safe experiment plan/result for one improvement opportunity. Does not apply changes.")
    experiment.add_argument("--opportunity", required=True, help="Path to opportunities.json, proposals.json, or a single opportunity JSON object.")
    experiment.add_argument("--id", required=True, help="Opportunity id, for example opp-0001.")
    experiment.add_argument("--out", required=True)
    experiment.add_argument("--run", action="store_true", help="Validate readiness for allowlisted deterministic experiment plans. Never executes arbitrary opportunity commands.")
    experiment.set_defaults(func=cmd_experiment)
    diff_preview = sub.add_parser("diff-preview", help="Create a preview-only change package from an experiment result. Does not edit files.")
    diff_preview.add_argument("--experiment", required=True, help="Experiment output directory, experiment-result.json, or experiment-plan.json.")
    diff_preview.add_argument("--hermes-home", required=True, help="Scanned Hermes home. Used only to block --out inside live Hermes inputs.")
    diff_preview.add_argument("--out", required=True)
    diff_preview.set_defaults(func=cmd_diff_preview)
    scan = sub.add_parser("scan")
    scan.add_argument("--hermes-home")
    group = scan.add_mutually_exclusive_group()
    group.add_argument("--profile")
    group.add_argument("--all-profiles", action="store_true")
    scan.add_argument("--kanban-db", help="Optional Kanban SQLite DB to import as aggregate metadata only.")
    scan.add_argument("--doctor-report", help="Optional existing Hermes/System Doctor report to import as a safe summary only.")
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
