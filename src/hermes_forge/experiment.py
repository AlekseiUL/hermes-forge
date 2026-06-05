from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_forge.paths import write_text_under
from hermes_forge.redaction import redact_json, safe_path_label

EXPERIMENT_PLAN_SCHEMA = "hermes-forge.experiment-plan/v1"
EXPERIMENT_RESULT_SCHEMA = "hermes-forge.experiment-result/v1"
EXPERIMENT_STATUSES = {"PLAN_ONLY", "READY_TO_RUN", "PASSED", "FAILED", "BLOCKED_NEEDS_OWNER_CONTEXT"}
RUNNABLE_NEXT_STEP_TYPES = {"create_eval"}
ALLOWLISTED_READINESS_COMMANDS = {
    "pytest -q tests/test_log_classifiers.py",
    "hermes-forge improve --mode read-only --hermes-home <fixture> --out <out>",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_opportunity(source: str, opportunity_id: str) -> dict[str, Any] | None:
    data = _load_json(Path(source).resolve())
    if "opportunities" in data:
        opportunities = data.get("opportunities", [])
    elif "proposals" in data:
        opportunities = data.get("proposals", [])
    elif data.get("id"):
        opportunities = [data]
    else:
        opportunities = []
    for item in opportunities:
        if item.get("id") == opportunity_id:
            return item
    return None


def classify_experiment(opportunity: dict[str, Any], *, run: bool) -> tuple[str, str, bool]:
    next_type = str(opportunity.get("safe_next_step_type", ""))
    state = str(opportunity.get("opportunity_state", ""))
    eval_plan = opportunity.get("eval_plan") if isinstance(opportunity.get("eval_plan"), dict) else {}
    command = str(eval_plan.get("command", ""))
    if next_type in {"ask_approval", "open_diff"} or state in {"needs_owner_decision", "ready_for_diff_preview"}:
        return "BLOCKED_NEEDS_OWNER_CONTEXT", "Opportunity needs owner approval or diff-preview context before an experiment can run.", False
    if next_type not in RUNNABLE_NEXT_STEP_TYPES:
        return "PLAN_ONLY", "This opportunity is useful as a review/watch plan, but has no deterministic experiment runner yet.", False
    runnable = command in ALLOWLISTED_READINESS_COMMANDS
    if not runnable:
        return "PLAN_ONLY", "Eval command is documented but not allowlisted for automatic readiness validation in this release.", False
    if not run:
        return "READY_TO_RUN", "Deterministic experiment plan is available; rerun with --run to validate readiness. v0.3.0 does not execute the documented command.", True
    return "READY_TO_RUN", "Deterministic experiment plan is allowlisted for readiness validation. v0.3.0 does not execute the documented command.", True


def _render_markdown(plan: dict[str, Any], result: dict[str, Any]) -> str:
    lines = [
        "# Hermes Forge experiment",
        "",
        "This is a safe experiment plan/result for one improvement opportunity. It is not an apply step.",
        "",
        "## Opportunity",
        f"- id: `{plan['opportunity_id']}`",
        f"- type: `{plan['opportunity_type']}`",
        f"- state: `{plan['opportunity_state']}`",
        f"- safe_next_step_type: `{plan['safe_next_step_type']}`",
        "",
        "## Hypothesis",
        plan["hypothesis"],
        "",
        "## Experiment",
        f"- status: `{result['status']}`",
        f"- run_requested: `{str(result['run_requested']).lower()}`",
        f"- runner_available: `{str(plan['runner_available']).lower()}`",
        f"- command: `{plan['eval_plan'].get('command', '')}`",
        f"- fixture: {plan['eval_plan'].get('fixture', '')}",
        f"- success_signal: {plan['eval_plan'].get('success_signal', '')}",
        "",
        "## Interpretation",
        result["interpretation"],
        "",
        "## Safety boundary",
        "- files_changed: `0`",
        "- apply_enabled: `false`",
        "- did not edit Hermes home;",
        "- did not restart gateways;",
        "- did not execute cron/plugin/MCP tools;",
        "- did not send platform messages.",
    ]
    if result.get("next_state"):
        lines.extend(["", "## Next state", f"- `{result['next_state']}`"])
    return "\n".join(lines) + "\n"


def run_experiment(*, opportunity_source: str, opportunity_id: str, out: str, run: bool = False) -> dict[str, Any]:
    out_dir = Path(out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    opportunity = load_opportunity(opportunity_source, opportunity_id)
    if opportunity is None:
        return {"ok": False, "status": "OPPORTUNITY_NOT_FOUND", "opportunity_id": opportunity_id}

    status, reason, runner_available = classify_experiment(opportunity, run=run)
    eval_plan = opportunity.get("eval_plan") if isinstance(opportunity.get("eval_plan"), dict) else {}
    plan = {
        "schema_version": EXPERIMENT_PLAN_SCHEMA,
        "generated_at": _now(),
        "opportunity_id": opportunity.get("id"),
        "finding_id": opportunity.get("finding_id"),
        "opportunity_type": opportunity.get("opportunity_type"),
        "proposal_type": opportunity.get("proposal_type"),
        "opportunity_state": opportunity.get("opportunity_state"),
        "safe_next_step_type": opportunity.get("safe_next_step_type"),
        "hypothesis": opportunity.get("improvement_hypothesis", ""),
        "evidence_ids": opportunity.get("evidence_ids", []),
        "eval_plan": {
            "schema_version": eval_plan.get("schema_version", "hermes-forge.eval-plan/v2"),
            "command": eval_plan.get("command", ""),
            "fixture": eval_plan.get("fixture", ""),
            "success_signal": eval_plan.get("success_signal", opportunity.get("success_criteria", "")),
            "writes_live_hermes_home": bool(eval_plan.get("writes_live_hermes_home", False)),
            "requires_approval_before_apply": bool(eval_plan.get("requires_approval_before_apply", True)),
        },
        "runner_available": runner_available,
        "runner_reason": reason,
        "allowed_side_effects": ["write_artifacts_to_out_dir"],
        "forbidden_side_effects": ["edit_hermes_home", "restart_gateway", "execute_cron", "execute_plugins", "execute_mcp", "apply_patches", "send_platform_messages", "read_secrets"],
    }

    # v0.3.0 runner is intentionally conservative: it never shells out to commands from an opportunity.
    # --run validates readiness only; actual built-in experiment execution can be added later.
    if status == "READY_TO_RUN" and run:
        result_status = "READY_TO_RUN"
        interpretation = "Readiness validation passed for an allowlisted experiment plan. v0.3.0 did not execute the documented command or change live files."
        next_state = "ready_for_experiment"
    elif status == "READY_TO_RUN":
        result_status = "READY_TO_RUN"
        interpretation = reason
        next_state = "ready_for_experiment"
    else:
        result_status = status
        interpretation = reason
        next_state = opportunity.get("opportunity_state")

    result = {
        "schema_version": EXPERIMENT_RESULT_SCHEMA,
        "generated_at": _now(),
        "opportunity_id": opportunity.get("id"),
        "status": result_status,
        "run_requested": run,
        "runner_available": runner_available,
        "files_changed": 0,
        "apply_enabled": False,
        "interpretation": interpretation,
        "next_state": next_state,
        "privacy": ["no_raw_logs", "no_command_args", "no_chat_ids", "no_secrets", "no_session_transcripts"],
    }

    write_text_under(out_dir / "experiment-plan.json", out_dir, json.dumps(redact_json(plan), ensure_ascii=False, indent=2))
    write_text_under(out_dir / "experiment-result.json", out_dir, json.dumps(redact_json(result), ensure_ascii=False, indent=2))
    write_text_under(out_dir / "checks.json", out_dir, json.dumps(redact_json({
        "schema_version": "hermes-forge.experiment-checks/v1",
        "checks": ["schema", "privacy", "no-live-apply", "no-gateway-restart", "no-cron-plugin-mcp-execution"],
        "stable_order": True,
    }), ensure_ascii=False, indent=2))
    write_text_under(out_dir / "expected-outcome.md", out_dir, f"# Expected outcome\n\n{plan['eval_plan'].get('success_signal', 'No success signal provided.')}\n")
    write_text_under(out_dir / "experiment.md", out_dir, _render_markdown(plan, result))
    return {"ok": True, "status": result_status, "out": safe_path_label(out_dir), "summary": {"opportunity_id": opportunity.get("id"), "runner_available": runner_available, "files_changed": 0, "apply_enabled": False}}
