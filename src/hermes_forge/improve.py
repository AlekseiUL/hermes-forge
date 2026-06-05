from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_forge.analysis import analyze_evidence
from hermes_forge.collectors.cron import collect_cron_evidence
from hermes_forge.collectors.doctor import collect_doctor_report_evidence
from hermes_forge.collectors.kanban import collect_kanban_evidence
from hermes_forge.collectors.logs import collect_log_evidence
from hermes_forge.collectors.profiles import discover_profiles
from hermes_forge.collectors.sessions import collect_session_evidence
from hermes_forge.collectors.skills import collect_skill_evidence
from hermes_forge.models import EvidenceItem, Finding
from hermes_forge.paths import is_under, resolve_hermes_home, write_text_under
from hermes_forge.redaction import redact_json, safe_path_label

IMPROVE_SCHEMA = "hermes-forge.improve-run/v1"
OPPORTUNITY_SCHEMA = "hermes-forge.opportunity/v1"
POLICY_SCHEMA = "hermes-forge.policy/v1"

OPPORTUNITY_MAP = {
    "profile_auth_or_provider_gap": {
        "opportunity_type": "config_review",
        "proposal_type": "question",
        "improvement_hypothesis": "Explicit provider/model routing and clearer auth-surface checks can reduce hidden model drift, cost surprises and failed background tasks.",
        "experiment": "Run a secret-safe provider/model audit, then compare before/after Forge findings and Hermes config-check output.",
        "success_criteria": "Provider/model findings drop or are reclassified as accepted risk without exposing secrets.",
        "safe_next_step": "Review provider/model presence by key names only; do not inspect credential values.",
    },
    "gateway_delivery_gap": {
        "opportunity_type": "observability_gap",
        "proposal_type": "experiment",
        "improvement_hypothesis": "Better delivery classification can separate harmless platform noise from real send/thread/topic failures.",
        "experiment": "Compare broad gateway markers with strict error-context counts over the same bounded log window.",
        "success_criteria": "The report identifies actionable delivery categories without raw logs or chat IDs.",
        "safe_next_step": "Use strict classifier counts first; avoid gateway restarts until a specific failing path is reproduced.",
    },
    "repeated_tool_failure": {
        "opportunity_type": "reliability_risk",
        "proposal_type": "experiment",
        "improvement_hypothesis": "Grouping repeated tool/runtime failures by safe attribution can reveal where guards, tests or UX messages should improve.",
        "experiment": "Track categories, exit codes and exception class names, then reproduce one top category with a fixture or bounded smoke command.",
        "success_criteria": "One top failure mode has a reproducible check and a proposed regression test before any code change.",
        "safe_next_step": "Do not patch wrappers yet; create a bounded reproduction or downgrade if evidence remains generic.",
    },
    "doctor_report_signal": {
        "opportunity_type": "system_health_review",
        "proposal_type": "eval_plan",
        "improvement_hypothesis": "Existing Doctor signals can become better improvement opportunities when correlated with Forge evidence instead of treated as standalone repair commands.",
        "experiment": "Import a Doctor summary and compare whether the same area appears in logs, cron, skills or sessions metadata.",
        "success_criteria": "Correlated Doctor findings receive higher confidence; uncorrelated findings are watch-only.",
        "safe_next_step": "Keep Doctor as summary input; do not run repair or restart from Forge.",
    },
    "kanban_workflow_signal": {
        "opportunity_type": "workflow_friction",
        "proposal_type": "hint",
        "improvement_hypothesis": "Workflow metadata can reveal stale, blocked or ambiguous operating states that reduce team throughput.",
        "experiment": "Review status buckets and compare them with the owner’s intended workflow contract.",
        "success_criteria": "Ambiguous or custom workflow states are either documented or intentionally ignored.",
        "safe_next_step": "Inspect aggregate buckets only; do not read private card bodies from Forge.",
    },
    "stale_skill_instruction": {
        "opportunity_type": "skill_improvement",
        "proposal_type": "repair_plan",
        "improvement_hypothesis": "Cleaner skill metadata improves discoverability, routing and safe reuse without rewriting behavior.",
        "experiment": "Patch only missing frontmatter/metadata in a fixture or review branch, then rerun Forge and skill listing checks.",
        "success_criteria": "The stale-skill finding disappears and no skill body/private linked content is exposed.",
        "safe_next_step": "Open frontmatter only; do not rewrite skill instructions unless separate evidence proves behavior drift.",
    },
    "cron_metadata_gap": {
        "opportunity_type": "automation_opportunity",
        "proposal_type": "question",
        "improvement_hypothesis": "Clearer cron ownership and status metadata can turn scheduled automation from hidden risk into accountable improvement loops.",
        "experiment": "Compare cron metadata before/after adding owner/intent/status conventions in a safe report.",
        "success_criteria": "Cron findings become explainable by status, owner and intended cadence without reading private job payloads.",
        "safe_next_step": "Review metadata only; do not pause, resume, edit or remove cron jobs from Forge.",
    },
    "session_history_signal": {
        "opportunity_type": "memory_hygiene",
        "proposal_type": "hint",
        "improvement_hypothesis": "Session metadata trends can show where reusable knowledge should become skills/docs instead of staying buried in chat history.",
        "experiment": "Compare recent session volume/topics against skill/docs coverage using metadata only.",
        "success_criteria": "Potential knowledge-capture opportunities are suggested without exporting session content.",
        "safe_next_step": "Use metadata counts only; do not read or publish transcripts.",
    },
}

DEFAULT_OPPORTUNITY = {
    "opportunity_type": "quality_gap",
    "proposal_type": "hint",
    "improvement_hypothesis": "Forge found a weak signal that may represent an improvement opportunity, but current evidence is not strong enough for a change.",
    "experiment": "Collect one more independent signal or rerun the scan after normal system activity.",
    "success_criteria": "The signal either repeats with stronger evidence or is downgraded to watch-only/false-positive.",
    "safe_next_step": "Keep this as a watch item until evidence improves.",
}


@dataclass
class Opportunity:
    id: str
    schema_version: str
    finding_id: str
    finding_type: str
    evidence_ids: list[str]
    opportunity_type: str
    proposal_type: str
    priority_score: int
    priority_label: str
    confidence: str
    confidence_reason: str
    improvement_hypothesis: str
    experiment: str
    success_criteria: str
    safe_next_step: str
    requires_approval: bool
    apply_forbidden_reason: str
    owner_role: str = "system_owner"
    reviewer_role: str = "reviewer"
    implementer_role: str = "implementer"
    approver_role: str = "approver"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _bump_next_id(next_id: int, evidence: list[EvidenceItem], batch: list[EvidenceItem]) -> int:
    evidence.extend(batch)
    return next_id + len(batch)


def collect_evidence(home: Path, *, profile: str | None, all_profiles: bool, kanban_db: Path | None, doctor_report: Path | None) -> tuple[dict[str, Any], list[EvidenceItem], dict[str, Any]]:
    inventory = discover_profiles(home, all_profiles=all_profiles, profile=profile)
    evidence: list[EvidenceItem] = []
    next_id = 1
    adapters: dict[str, dict[str, object]] = {
        "profiles": {"status": "enabled"},
        "skills": {"status": "enabled"},
        "cron": {"status": "enabled"},
        "logs": {"status": "enabled"},
        "sessions": {"status": "enabled", "mode": "metadata_only"},
        "kanban": {"status": "enabled" if kanban_db else "not_configured", "mode": "metadata_only"},
        "doctor_report": {"status": "enabled" if doctor_report else "not_configured", "mode": "safe_summary_only"},
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
    next_id = _bump_next_id(next_id, evidence, collect_kanban_evidence(kanban_db, home, next_id))
    next_id = _bump_next_id(next_id, evidence, collect_doctor_report_evidence(doctor_report, home, next_id))
    inventory["adapters"] = adapters
    return inventory, evidence, adapters


def opportunities_from_findings(findings: list[Finding]) -> list[Opportunity]:
    out: list[Opportunity] = []
    for idx, finding in enumerate(findings, 1):
        tpl = OPPORTUNITY_MAP.get(finding.type, DEFAULT_OPPORTUNITY)
        out.append(Opportunity(
            id=f"opp-{idx:04d}",
            schema_version=OPPORTUNITY_SCHEMA,
            finding_id=finding.id,
            finding_type=finding.type,
            evidence_ids=finding.evidence_ids,
            opportunity_type=str(tpl["opportunity_type"]),
            proposal_type=str(tpl["proposal_type"]),
            priority_score=finding.priority_score,
            priority_label=finding.priority_label,
            confidence=finding.confidence,
            confidence_reason=finding.priority_reason,
            improvement_hypothesis=str(tpl["improvement_hypothesis"]),
            experiment=str(tpl["experiment"]),
            success_criteria=str(tpl["success_criteria"]),
            safe_next_step=str(tpl["safe_next_step"]),
            requires_approval=str(tpl["proposal_type"]) in {"repair_plan", "patch_candidate", "config_review"},
            apply_forbidden_reason="Read-only improve mode never applies changes. Generate candidates and ask for approval before modifying a Hermes installation.",
        ))
    return out


def dedup_opportunities(opportunities: list[Opportunity]) -> dict[str, Any]:
    groups: dict[str, list[Opportunity]] = {}
    for opp in opportunities:
        groups.setdefault(opp.opportunity_type, []).append(opp)
    payload_groups = []
    for idx, (opportunity_type, items) in enumerate(sorted(groups.items()), 1):
        lead = sorted(items, key=lambda o: (-o.priority_score, o.id))[0]
        payload_groups.append({
            "id": f"dedup-{idx:04d}",
            "opportunity_type": opportunity_type,
            "lead_opportunity_id": lead.id,
            "opportunity_ids": [o.id for o in sorted(items, key=lambda o: o.id)],
            "count": len(items),
            "dedup_reason": "Grouped by universal improvement opportunity type.",
        })
    return {"schema_version": "hermes-forge.dedup/v1", "groups": payload_groups}


def _render_report(run: dict[str, Any], opportunities: list[Opportunity], dedup: dict[str, Any], evidence_count: int) -> str:
    lines = [
        "# Hermes Forge improvement report",
        "",
        "Forge checked this Hermes installation for improvement opportunities, not just failures.",
        "",
        "## Summary",
        f"- mode: `{run['mode']}`",
        f"- generated_at: `{run['generated_at']}`",
        f"- profiles_checked: `{run['profiles_checked']}`",
        f"- evidence_items: `{evidence_count}`",
        f"- findings: `{run['findings']}`",
        f"- opportunities_total: `{run['opportunities']}`",
        f"- opportunities_shown: `{len(opportunities)}`",
        f"- files_changed: `0`",
        "- apply_enabled: `false`",
        "",
        "## Top opportunities",
    ]
    if not opportunities:
        lines.extend([
            "- No improvement opportunities were found from the current evidence.",
            "",
            "## No-change interpretation",
            "Current evidence is insufficient for a useful change. Keep the run as a baseline and compare future runs against it.",
        ])
    else:
        for opp in sorted(opportunities, key=lambda o: (-o.priority_score, o.id)):
            lines.extend([
                f"### {opp.id} / {opp.opportunity_type}",
                f"- proposal_type: `{opp.proposal_type}`",
                f"- priority: `{opp.priority_label}` / `{opp.priority_score}`",
                f"- evidence: `{', '.join(opp.evidence_ids)}`",
                f"- hypothesis: {opp.improvement_hypothesis}",
                f"- experiment: {opp.experiment}",
                f"- success_criteria: {opp.success_criteria}",
                f"- safe_next_step: {opp.safe_next_step}",
                "",
            ])
    questions = [o for o in opportunities if o.proposal_type == "question"]
    experiments = [o for o in opportunities if o.proposal_type in {"experiment", "eval_plan"}]
    plans = [o for o in opportunities if o.proposal_type in {"repair_plan", "patch_candidate"}]
    lines.extend(["## Questions for the system owner"])
    if questions:
        for opp in questions[:5]:
            lines.append(f"- {opp.id}: Confirm whether `{opp.opportunity_type}` should be treated as an improvement target or accepted risk.")
    else:
        lines.append("- None from this run.")
    lines.extend(["", "## Suggested experiments / evals"])
    if experiments:
        for opp in experiments[:5]:
            lines.append(f"- {opp.id}: {opp.experiment}")
    else:
        lines.append("- None from this run.")
    lines.extend(["", "## Candidate changes"])
    if plans:
        for opp in plans[:5]:
            lines.append(f"- {opp.id}: {opp.safe_next_step}")
    else:
        lines.append("- No file-change candidate is recommended from read-only evidence.")
    lines.extend([
        "",
        "## Dedup groups",
    ])
    groups = dedup.get("groups", [])
    if groups:
        for group in groups:
            lines.append(f"- {group['id']}: `{group['opportunity_type']}` count={group['count']} lead={group['lead_opportunity_id']}")
    else:
        lines.append("- No duplicate groups.")
    lines.extend([
        "",
        "## What Forge checked",
        "- profile inventory and safe profile metadata;",
        "- skills frontmatter metadata;",
        "- cron metadata;",
        "- bounded runtime log classifiers;",
        "- session metadata only;",
        "- optional Kanban and Doctor summaries if provided.",
        "",
        "## What Forge did not do",
        "- did not edit files;",
        "- did not read secrets or auth payloads;",
        "- did not export raw logs, chat IDs, command args or session transcripts;",
        "- did not restart gateways or execute cron/plugin/MCP tools;",
        "- did not apply patches.",
        "",
        "## Safety boundary",
        "This report is read-only. Treat opportunities as evidence-backed improvement candidates. Any real change needs a separate approval gate, diff preview, tests and rollback plan.",
    ])
    return "\n".join(lines) + "\n"


def run_improve(*, hermes_home: str | None, out: str, profile: str | None = None, all_profiles: bool = False, kanban_db: str | None = None, doctor_report: str | None = None, top: int = 7, mode: str = "read-only") -> dict[str, Any]:
    if mode != "read-only":
        return {"ok": False, "status": "UNSUPPORTED_MODE", "mode": mode, "supported_modes": ["read-only"]}
    if top < 1:
        return {"ok": False, "status": "INVALID_TOP", "reason": "--top must be >= 1", "top": top}
    home = resolve_hermes_home(hermes_home)
    out_dir = Path(out).resolve()
    if is_under(out_dir, home):
        return {"ok": False, "status": "OUT_UNDER_HERMES_HOME_BLOCKED", "reason": "Forge writes only outside the scanned Hermes home."}
    out_dir.mkdir(parents=True, exist_ok=True)
    selected_all = bool(all_profiles or not profile)
    inventory, evidence, adapters = collect_evidence(
        home,
        profile=profile,
        all_profiles=selected_all,
        kanban_db=Path(kanban_db) if kanban_db else None,
        doctor_report=Path(doctor_report) if doctor_report else None,
    )
    findings = analyze_evidence(evidence)
    opportunities = opportunities_from_findings(findings)
    dedup = dedup_opportunities(opportunities)
    run = {
        "schema_version": IMPROVE_SCHEMA,
        "generated_at": _now(),
        "mode": mode,
        "hermes_home": safe_path_label(home),
        "profile": profile or ("all" if selected_all else "default"),
        "profiles_checked": len(inventory.get("profiles", [])),
        "evidence_items": len(evidence),
        "findings": len(findings),
        "opportunities": len(opportunities),
        "top": top,
        "apply_enabled": False,
        "files_changed": 0,
        "output_policy": "local_private_by_default_share_after_review",
    }
    policy = {
        "schema_version": POLICY_SCHEMA,
        "mode": mode,
        "read_only": True,
        "allowed_side_effects": ["write_artifacts_to_out_dir"],
        "forbidden_side_effects": ["edit_hermes_home", "read_secrets", "raw_log_export", "restart_gateway", "execute_cron", "execute_plugins", "execute_mcp", "apply_patches", "send_platform_messages"],
        "privacy": ["metadata_only", "category_counts_only", "safe_summary_only", "no_raw_logs", "no_chat_ids", "no_command_args", "no_session_transcripts"],
    }
    summary = {
        "schema_version": "hermes-forge.improve-summary/v1",
        "run": run,
        "adapters": adapters,
        "evidence_by_source": {},
        "opportunity_by_type": {},
        "proposal_by_type": {},
    }
    for item in evidence:
        summary["evidence_by_source"][item.source_type] = summary["evidence_by_source"].get(item.source_type, 0) + 1
    for opp in opportunities:
        summary["opportunity_by_type"][opp.opportunity_type] = summary["opportunity_by_type"].get(opp.opportunity_type, 0) + 1
        summary["proposal_by_type"][opp.proposal_type] = summary["proposal_by_type"].get(opp.proposal_type, 0) + 1

    write_text_under(out_dir / "run.json", out_dir, json.dumps(redact_json(run), ensure_ascii=False, indent=2))
    write_text_under(out_dir / "policy.json", out_dir, json.dumps(redact_json(policy), ensure_ascii=False, indent=2))
    write_text_under(out_dir / "inventory.json", out_dir, json.dumps(redact_json(inventory), ensure_ascii=False, indent=2))
    write_text_under(out_dir / "evidence-ledger.jsonl", out_dir, "\n".join(json.dumps(redact_json(e.to_dict()), ensure_ascii=False) for e in evidence) + ("\n" if evidence else ""))
    write_text_under(out_dir / "findings.json", out_dir, json.dumps(redact_json({"schema_version": "hermes-forge.findings/v1", "findings": [f.to_dict() for f in findings]}), ensure_ascii=False, indent=2))
    write_text_under(out_dir / "dedup-groups.json", out_dir, json.dumps(redact_json(dedup), ensure_ascii=False, indent=2))
    write_text_under(out_dir / "opportunities.json", out_dir, json.dumps(redact_json({"schema_version": "hermes-forge.opportunities/v1", "opportunities": [o.to_dict() for o in opportunities]}), ensure_ascii=False, indent=2))
    write_text_under(out_dir / "proposals.json", out_dir, json.dumps(redact_json({"schema_version": "hermes-forge.proposals/v2", "proposals": [o.to_dict() for o in opportunities]}), ensure_ascii=False, indent=2))
    write_text_under(out_dir / "scan-summary.json", out_dir, json.dumps(redact_json(summary), ensure_ascii=False, indent=2))
    write_text_under(out_dir / "redaction-report.json", out_dir, json.dumps({"schema_version": "hermes-forge.redaction-report/v1", "redaction_enabled": True}, indent=2))
    write_text_under(out_dir / "report.md", out_dir, _render_report(run, sorted(opportunities, key=lambda o: (-o.priority_score, o.id))[:top], dedup, len(evidence)))
    return {"ok": True, "status": "OK", "out": safe_path_label(out_dir, home), "summary": summary}
