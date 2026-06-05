from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_forge.paths import is_under, resolve_hermes_home, write_text_under
from hermes_forge.redaction import redact_json, safe_path_label

APPLY_PLAN_SCHEMA = "hermes-forge.apply-plan/v1"
BACKUP_MANIFEST_SCHEMA = "hermes-forge.backup-manifest/v1"
APPLY_RESULT_SCHEMA = "hermes-forge.apply-result/v1"
SUPPORTED_CANDIDATE_STATUS = "CANDIDATE_PATCH_PREVIEW_ONLY"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_candidate(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("candidate must be a JSON object")
    return data


def _approval_id(candidate: dict[str, Any]) -> str:
    explicit = candidate.get("approval_id")
    if explicit:
        return str(explicit)
    virtual_path = candidate.get("virtual_path")
    if virtual_path:
        return f"approve:{virtual_path}"
    return "approve:unknown"


def _render_plan_md(plan: dict[str, Any], result: dict[str, Any]) -> str:
    lines = [
        "# Hermes Forge apply gate plan",
        "",
        "This is a gated apply skeleton. No executor was run and no live file was changed.",
        "",
        "## Status",
        f"- status: `{result['status']}`",
        f"- files_changed: `{result['files_changed']}`",
        f"- apply_enabled: `{str(result['apply_enabled']).lower()}`",
        "",
        "## Candidate",
        f"- approval_id: `{plan['approval_id']}`",
        f"- candidate_status: `{plan['candidate_status']}`",
        f"- virtual_path: `{plan['virtual_path']}`",
        f"- live_target: `{plan['live_target']}`",
        "",
        "## Gates checked",
    ]
    for gate in plan["gates"]:
        lines.append(f"- {gate['name']}: `{gate['status']}`")
    lines.extend([
        "",
        "## Why blocked",
        result["reason"],
        "",
        "## Safety boundary",
        "- no live Hermes edit;",
        "- no patch application;",
        "- no gateway restart;",
        "- no cron/plugin/MCP execution;",
        "- no platform message;",
        "- no secret read.",
    ])
    return "\n".join(lines) + "\n"


def run_apply_gate(*, candidate_path: str, approve: str | None, live_target: str | None, hermes_home: str, out: str) -> dict[str, Any]:
    home = resolve_hermes_home(hermes_home)
    out_dir = Path(out).resolve()
    if is_under(out_dir, home):
        return {"ok": False, "status": "OUT_UNDER_HERMES_HOME_BLOCKED", "reason": "Forge apply writes only outside the scanned Hermes home."}

    candidate_file = Path(candidate_path).resolve()
    try:
        candidate = _load_candidate(candidate_file)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "status": "INVALID_CANDIDATE", "reason": str(exc)}

    approval_id = _approval_id(candidate)
    gates: list[dict[str, Any]] = []

    candidate_status = str(candidate.get("status", ""))
    gates.append({"name": "candidate_status", "status": "pass" if candidate_status == SUPPORTED_CANDIDATE_STATUS else "fail", "expected": SUPPORTED_CANDIDATE_STATUS, "actual": candidate_status})
    gates.append({"name": "candidate_preview_only", "status": "pass" if candidate.get("files_changed") == 0 and candidate.get("apply_enabled") is False and candidate.get("live_path") is None else "fail"})
    gates.append({"name": "approval", "status": "pass" if approve == approval_id else "fail", "expected": approval_id, "actual": "provided" if approve else "missing"})

    target_label = None
    if live_target:
        target_path = Path(live_target).expanduser().resolve()
        target_under_home = is_under(target_path, home)
        target_label = safe_path_label(target_path, home)
    else:
        target_path = None
        target_under_home = False
        target_label = None
    gates.append({"name": "live_target_explicit", "status": "pass" if bool(live_target) else "fail"})
    gates.append({"name": "live_target_under_hermes_home", "status": "pass" if target_under_home else "fail"})
    gates.append({"name": "executor_registered", "status": "fail", "reason": "No apply executor is registered in this release."})

    out_dir.mkdir(parents=True, exist_ok=True)
    all_pre_executor_gates_pass = all(g["status"] == "pass" for g in gates if g["name"] != "executor_registered")
    status = "APPLY_BLOCKED_NO_EXECUTOR" if all_pre_executor_gates_pass else "APPLY_BLOCKED_PRECHECK_FAILED"
    reason = "No apply executor is registered in this release, so Forge stopped before any mutation." if all_pre_executor_gates_pass else "One or more apply prechecks failed; Forge stopped before any mutation."

    plan = {
        "schema_version": APPLY_PLAN_SCHEMA,
        "generated_at": _now(),
        "candidate": safe_path_label(candidate_file, home),
        "candidate_status": candidate_status,
        "approval_id": approval_id,
        "approval_matched": approve == approval_id,
        "virtual_path": candidate.get("virtual_path"),
        "live_target": target_label,
        "live_target_required": True,
        "backup_required_before_executor": True,
        "backup_created": False,
        "gates": gates,
        "files_changed": 0,
        "apply_enabled": False,
    }
    backup_manifest = {
        "schema_version": BACKUP_MANIFEST_SCHEMA,
        "status": "BACKUP_NOT_CREATED_NO_EXECUTOR" if all_pre_executor_gates_pass else "BACKUP_NOT_CREATED_PRECHECK_FAILED",
        "reason": "This skeleton does not copy live files. A future executor must create a backup before mutation.",
        "live_target": target_label,
        "files_backed_up": 0,
    }
    result = {
        "schema_version": APPLY_RESULT_SCHEMA,
        "ok": False,
        "status": status,
        "reason": reason,
        "out": safe_path_label(out_dir, home),
        "files_changed": 0,
        "apply_enabled": False,
        "executor_ran": False,
        "backup_created": False,
    }

    redacted_plan = redact_json(plan)
    redacted_backup = redact_json(backup_manifest)
    redacted_result = redact_json(result)
    try:
        write_text_under(out_dir / "apply-plan.json", out_dir, json.dumps(redacted_plan, ensure_ascii=False, indent=2))
        write_text_under(out_dir / "backup-manifest.json", out_dir, json.dumps(redacted_backup, ensure_ascii=False, indent=2))
        write_text_under(out_dir / "apply-result.json", out_dir, json.dumps(redacted_result, ensure_ascii=False, indent=2))
        write_text_under(out_dir / "apply-plan.md", out_dir, _render_plan_md(redacted_plan, redacted_result))
    except (OSError, ValueError) as exc:
        return redact_json({
            "schema_version": APPLY_RESULT_SCHEMA,
            "ok": False,
            "status": "APPLY_ARTIFACT_WRITE_BLOCKED",
            "reason": str(exc),
            "out": safe_path_label(out_dir, home),
            "files_changed": 0,
            "apply_enabled": False,
            "executor_ran": False,
            "backup_created": False,
        })
    return redacted_result
