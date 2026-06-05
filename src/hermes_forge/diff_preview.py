from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_forge.paths import is_under, resolve_hermes_home, write_text_under
from hermes_forge.redaction import redact_json, safe_path_label

DIFF_PREVIEW_SCHEMA = "hermes-forge.diff-preview/v1"
RISK_SCHEMA = "hermes-forge.diff-risk/v1"

DIFFABLE_EXPERIMENT_STATUSES = {"READY_TO_RUN", "PASSED"}
DIFFABLE_NEXT_STATES = {"ready_for_experiment", "ready_for_diff_preview"}
DIFF_PREVIEW_TYPES = {
    "skill_improvement": "metadata_patch_preview",
    "reliability_risk": "test_or_guard_preview",
    "observability_gap": "classifier_or_report_preview",
    "config_review": "config_review_preview",
    "automation_opportunity": "metadata_convention_preview",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_experiment(source: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
    path = Path(source).resolve()
    if path.is_dir():
        plan_path = path / "experiment-plan.json"
        result_path = path / "experiment-result.json"
    elif path.name == "experiment-result.json":
        result_path = path
        plan_path = path.parent / "experiment-plan.json"
    elif path.name == "experiment-plan.json":
        plan_path = path
        result_path = path.parent / "experiment-result.json"
    else:
        raise ValueError("--experiment must be an experiment output directory, experiment-result.json, or experiment-plan.json")
    if not plan_path.exists() or not result_path.exists():
        raise FileNotFoundError("experiment-plan.json and experiment-result.json must both exist")
    return _load_json(plan_path), _load_json(result_path), plan_path.parent


def classify_diff_preview(plan: dict[str, Any], result: dict[str, Any]) -> tuple[str, str, str]:
    status = str(result.get("status", ""))
    next_state = str(result.get("next_state", ""))
    opportunity_type = str(plan.get("opportunity_type", ""))
    if status == "BLOCKED_NEEDS_OWNER_CONTEXT":
        return "BLOCKED_NEEDS_OWNER_CONTEXT", "Owner decision is required before a diff preview is useful.", "blocked"
    if status == "PLAN_ONLY":
        return "PLAN_ONLY", "The experiment is plan-only; collect stronger evidence or owner context before previewing a diff.", "no_change"
    if status not in DIFFABLE_EXPERIMENT_STATUSES or next_state not in DIFFABLE_NEXT_STATES:
        return "BLOCKED_NOT_READY", "Experiment result is not ready for diff preview.", "blocked"
    preview_type = DIFF_PREVIEW_TYPES.get(opportunity_type, "review_note_preview")
    return "PREVIEW_ONLY", "Diff preview is safe to draft, but no files are changed in v0.4.0.", preview_type


def _suggested_targets(plan: dict[str, Any], preview_type: str) -> list[dict[str, Any]]:
    opportunity_type = str(plan.get("opportunity_type", "unknown"))
    if preview_type == "metadata_patch_preview":
        return [{"target_kind": "skill_frontmatter", "path_policy": "review-selected-skill-only", "change_kind": "metadata_only", "live_path": None}]
    if preview_type == "test_or_guard_preview":
        return [{"target_kind": "test_fixture_or_guard", "path_policy": "synthetic-test-first", "change_kind": "test_or_guard", "live_path": None}]
    if preview_type == "classifier_or_report_preview":
        return [{"target_kind": "classifier_or_report", "path_policy": "source-controlled-code-only", "change_kind": "classifier/report wording", "live_path": None}]
    if preview_type == "config_review_preview":
        return [{"target_kind": "config_review_note", "path_policy": "no-live-config-edit", "change_kind": "review_note", "live_path": None}]
    if preview_type == "metadata_convention_preview":
        return [{"target_kind": "automation_metadata", "path_policy": "review-only-no-cron-edit", "change_kind": "metadata_convention", "live_path": None}]
    return [{"target_kind": opportunity_type, "path_policy": "review-only", "change_kind": "review_note", "live_path": None}]


def _render_diff_preview_md(payload: dict[str, Any], risk: dict[str, Any], rollback: str, tests: list[str]) -> str:
    lines = [
        "# Hermes Forge diff preview",
        "",
        "This is a preview package only. Forge did not edit the Hermes installation or source files.",
        "",
        "## Summary",
        f"- status: `{payload['status']}`",
        f"- opportunity_id: `{payload['opportunity_id']}`",
        f"- opportunity_type: `{payload['opportunity_type']}`",
        f"- preview_type: `{payload['preview_type']}`",
        f"- files_changed: `{payload['files_changed']}`",
        f"- apply_enabled: `{str(payload['apply_enabled']).lower()}`",
        "",
        "## Proposed change shape",
    ]
    if payload["proposed_files"]:
        for item in payload["proposed_files"]:
            lines.extend([
                f"- target_kind: `{item['target_kind']}`",
                f"  - change_kind: `{item['change_kind']}`",
                f"  - path_policy: `{item['path_policy']}`",
                "  - live_path: `null`",
            ])
    else:
        lines.append("- No file change is suggested from the current experiment state.")
    lines.extend([
        "",
        "## Why",
        payload["rationale"],
        "",
        "## Risk check",
        f"- risk_level: `{risk['risk_level']}`",
        f"- needs_owner_approval: `{str(risk['needs_owner_approval']).lower()}`",
        f"- reason: {risk['reason']}",
        "",
        "## Tests to run",
    ])
    for test in tests:
        lines.append(f"- `{test}`")
    lines.extend([
        "",
        "## Rollback plan",
        rollback,
        "",
        "## Safety boundary",
        "- did not apply changes;",
        "- did not write to Hermes home;",
        "- did not execute cron/plugin/MCP tools;",
        "- did not restart gateways;",
        "- did not send platform messages.",
    ])
    return "\n".join(lines) + "\n"


def run_diff_preview(*, experiment: str, out: str, hermes_home: str | None = None) -> dict[str, Any]:
    home = resolve_hermes_home(hermes_home)
    out_dir = Path(out).resolve()
    if is_under(out_dir, home):
        return {"ok": False, "status": "OUT_UNDER_HERMES_HOME_BLOCKED", "reason": "Forge diff-preview writes only outside the scanned Hermes home."}
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        plan, result, source_dir = load_experiment(experiment)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "status": "INVALID_EXPERIMENT", "reason": str(exc)}

    status, reason, preview_type = classify_diff_preview(plan, result)
    proposed_files = _suggested_targets(plan, preview_type) if status == "PREVIEW_ONLY" else []
    tests_to_run = [
        "python -m pytest -q",
        "python scripts/privacy_scan.py .",
        "hermes-forge improve --mode read-only --hermes-home <fixture> --out <out>",
    ]
    rollback = "No rollback is needed for this preview because Forge changed zero files. If a future apply step uses this preview, create a backup/checkpoint before applying and restore that checkpoint on test failure."
    payload = {
        "schema_version": DIFF_PREVIEW_SCHEMA,
        "generated_at": _now(),
        "status": status,
        "reason": reason,
        "experiment_source": safe_path_label(source_dir),
        "opportunity_id": plan.get("opportunity_id"),
        "finding_id": plan.get("finding_id"),
        "opportunity_type": plan.get("opportunity_type"),
        "preview_type": preview_type,
        "rationale": plan.get("hypothesis", ""),
        "evidence_ids": plan.get("evidence_ids", []),
        "proposed_files": proposed_files,
        "files_changed": 0,
        "apply_enabled": False,
        "requires_approval_before_apply": True,
        "forbidden_side_effects": ["edit_hermes_home", "apply_patches", "restart_gateway", "execute_cron", "execute_plugins", "execute_mcp", "send_platform_messages", "read_secrets"],
    }
    risk = {
        "schema_version": RISK_SCHEMA,
        "risk_level": "blocked" if status.startswith("BLOCKED") else ("low" if status == "PREVIEW_ONLY" else "watch"),
        "needs_owner_approval": True,
        "reason": "Preview only. Any real file edit requires a separate approval gate, backup, tests and rollback plan.",
        "files_changed": 0,
        "apply_enabled": False,
    }
    redacted_payload = redact_json(payload)
    redacted_risk = redact_json(risk)
    write_text_under(out_dir / "diff-preview.json", out_dir, json.dumps(redacted_payload, ensure_ascii=False, indent=2))
    write_text_under(out_dir / "proposed-files.json", out_dir, json.dumps(redact_json({"schema_version": "hermes-forge.proposed-files/v1", "files": proposed_files}), ensure_ascii=False, indent=2))
    write_text_under(out_dir / "risk-check.json", out_dir, json.dumps(redacted_risk, ensure_ascii=False, indent=2))
    write_text_under(out_dir / "tests-to-run.md", out_dir, "# Tests to run\n\n" + "\n".join(f"- `{test}`" for test in tests_to_run) + "\n")
    write_text_under(out_dir / "rollback-plan.md", out_dir, "# Rollback plan\n\n" + rollback + "\n")
    write_text_under(out_dir / "diff-preview.md", out_dir, _render_diff_preview_md(redacted_payload, redacted_risk, rollback, tests_to_run))
    return {"ok": True, "status": status, "out": safe_path_label(out_dir), "summary": {"opportunity_id": plan.get("opportunity_id"), "preview_type": preview_type, "files_changed": 0, "apply_enabled": False}}
