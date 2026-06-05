from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hermes_forge.paths import ensure_under, is_under, resolve_hermes_home, write_text_under
from hermes_forge.redaction import redact_json, safe_path_label

APPLY_PLAN_SCHEMA = "hermes-forge.apply-plan/v1"
BACKUP_MANIFEST_SCHEMA = "hermes-forge.backup-manifest/v1"
APPLY_RESULT_SCHEMA = "hermes-forge.apply-result/v1"
SUPPORTED_CANDIDATE_STATUS = "CANDIDATE_PATCH_PREVIEW_ONLY"
SUPPORTED_EXECUTOR = "skill_frontmatter_metadata_v1"
ALLOWED_FRONTMATTER_PATCH_KEYS = {"description", "tags", "version", "category"}


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


def _has_symlink_parent(path: Path, stop: Path) -> bool:
    current = path
    stop_resolved = stop.resolve()
    while True:
        if current.is_symlink():
            return True
        if current.resolve() == stop_resolved:
            return False
        if current.parent == current:
            return False
        current = current.parent


def _format_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    text = str(value)
    if re.fullmatch(r"[A-Za-z0-9_.:/@ -]{0,240}", text) and "\n" not in text:
        return json.dumps(text, ensure_ascii=False)
    raise ValueError("frontmatter scalar contains unsupported characters")


def _validate_frontmatter_patch(patch: Any) -> dict[str, Any]:
    if not isinstance(patch, dict) or not patch:
        raise ValueError("frontmatter_patch must be a non-empty object")
    unknown = set(patch) - ALLOWED_FRONTMATTER_PATCH_KEYS
    if unknown:
        raise ValueError("frontmatter_patch contains unsupported keys")
    clean: dict[str, Any] = {}
    if "description" in patch:
        value = patch["description"]
        if not isinstance(value, str) or not value.strip() or len(value) > 500 or "\n" in value:
            raise ValueError("description must be a non-empty single-line string up to 500 characters")
        clean["description"] = value.strip()
    if "category" in patch:
        value = patch["category"]
        if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value):
            raise ValueError("category must be a short slug")
        clean["category"] = value
    if "version" in patch:
        value = patch["version"]
        if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9_.-]+)?", value):
            raise ValueError("version must be a semantic-version-like string")
        clean["version"] = value
    if "tags" in patch:
        value = patch["tags"]
        if not isinstance(value, list) or len(value) > 20:
            raise ValueError("tags must be a list with at most 20 items")
        tags = []
        for item in value:
            if not isinstance(item, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", item):
                raise ValueError("tags must be short slugs")
            tags.append(item)
        clean["tags"] = tags
    return clean


def _render_patch_lines(patch: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key in sorted(patch):
        value = patch[key]
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {_format_scalar(item)}" for item in value)
        else:
            lines.append(f"{key}: {_format_scalar(value)}")
    return lines


def _apply_frontmatter_patch(text: str, patch: dict[str, Any]) -> str:
    lines = text.splitlines()
    trailing_newline = text.endswith("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration as exc:
        raise ValueError("SKILL.md frontmatter terminator not found") from exc
    frontmatter = lines[1:end]
    body = lines[end + 1 :]
    patch_keys = set(patch)
    kept: list[str] = []
    i = 0
    key_line = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:")
    while i < len(frontmatter):
        line = frontmatter[i]
        match = key_line.match(line)
        if match and match.group(1) in patch_keys:
            i += 1
            while i < len(frontmatter) and (frontmatter[i].startswith(" ") or frontmatter[i].startswith("\t")):
                i += 1
            continue
        kept.append(line)
        i += 1
    new_lines = ["---", *kept, *_render_patch_lines(patch), "---", *body]
    return "\n".join(new_lines) + ("\n" if trailing_newline else "")


def _render_plan_md(plan: dict[str, Any], result: dict[str, Any]) -> str:
    title = "Hermes Forge apply result" if result.get("executor_ran") else "Hermes Forge apply gate plan"
    lines = [
        f"# {title}",
        "",
        "Forge only runs registered bounded executors. Arbitrary diffs are not applied.",
        "",
        "## Status",
        f"- status: `{result['status']}`",
        f"- files_changed: `{result['files_changed']}`",
        f"- apply_enabled: `{str(result['apply_enabled']).lower()}`",
        f"- executor_ran: `{str(result.get('executor_ran', False)).lower()}`",
        "",
        "## Candidate",
        f"- approval_id: `{plan['approval_id']}`",
        f"- candidate_status: `{plan['candidate_status']}`",
        f"- executor_id: `{plan.get('executor_id')}`",
        f"- virtual_path: `{plan['virtual_path']}`",
        f"- live_target: `{plan['live_target']}`",
        "",
        "## Gates checked",
    ]
    for gate in plan["gates"]:
        lines.append(f"- {gate['name']}: `{gate['status']}`")
    lines.extend(["", "## Result", result["reason"], "", "## Safety boundary"])
    if result.get("executor_ran"):
        lines.extend([
            "- changed exactly one approved `SKILL.md`;",
            "- changed frontmatter metadata only;",
            "- created local backup before mutation;",
        ])
    else:
        lines.extend([
            "- no live Hermes edit;",
            "- no patch application;",
        ])
    lines.extend([
        "- no gateway restart;",
        "- no cron/plugin/MCP execution;",
        "- no platform message;",
        "- no secret read.",
    ])
    return "\n".join(lines) + "\n"


def _preflight_artifact_paths(out_dir: Path, relative_paths: list[str]) -> None:
    for rel in relative_paths:
        path = out_dir / rel
        if path.is_symlink():
            raise ValueError("refusing to overwrite symlink artifact")
        target = ensure_under(path, out_dir)
        if target.exists():
            stat = target.stat()
            if getattr(stat, "st_nlink", 1) > 1:
                raise ValueError("refusing to overwrite hardlinked artifact")


def _write_apply_artifacts(out_dir: Path, home: Path, plan: dict[str, Any], backup_manifest: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
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


def _execute_skill_frontmatter_metadata(*, target_path: Path, home: Path, out_dir: Path, candidate: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if target_path.name != "SKILL.md":
        raise ValueError("skill_frontmatter_metadata_v1 requires a SKILL.md live target")
    if target_path.is_symlink() or _has_symlink_parent(target_path, home):
        raise ValueError("refusing to execute on symlinked live target")
    if not target_path.exists() or not target_path.is_file():
        raise ValueError("live target must be an existing file")
    if getattr(target_path.stat(), "st_nlink", 1) > 1:
        raise ValueError("refusing to execute on hardlinked live target")
    original = target_path.read_text(encoding="utf-8")
    patch = _validate_frontmatter_patch(candidate.get("frontmatter_patch"))
    updated = _apply_frontmatter_patch(original, patch)
    if updated == original:
        raise ValueError("frontmatter patch produced no change")

    backup_rel = Path("backups") / "target-before.txt"
    write_text_under(out_dir / backup_rel, out_dir, original)
    backup_manifest = {
        "schema_version": BACKUP_MANIFEST_SCHEMA,
        "status": "BACKUP_CREATED",
        "reason": "Local private backup created before bounded frontmatter metadata mutation.",
        "live_target": safe_path_label(target_path, home),
        "backup": safe_path_label(out_dir / backup_rel, home),
        "files_backed_up": 1,
    }
    try:
        target_path.write_text(updated, encoding="utf-8")
        verified = target_path.read_text(encoding="utf-8")
        _apply_frontmatter_patch(verified, {}) if False else None
    except Exception:
        target_path.write_text(original, encoding="utf-8")
        raise

    result = {
        "schema_version": APPLY_RESULT_SCHEMA,
        "ok": True,
        "status": "APPLY_EXECUTED",
        "reason": "skill_frontmatter_metadata_v1 applied a bounded frontmatter metadata patch after approval.",
        "out": safe_path_label(out_dir, home),
        "files_changed": 1,
        "apply_enabled": True,
        "executor_ran": True,
        "executor_id": SUPPORTED_EXECUTOR,
        "backup_created": True,
    }
    plan["backup_created"] = True
    plan["files_changed"] = 1
    plan["apply_enabled"] = True
    return backup_manifest, result


def run_apply_gate(*, candidate_path: str, approve: str | None, live_target: str | None, hermes_home: str, out: str, execute: bool = False) -> dict[str, Any]:
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
    executor_id = str(candidate.get("executor_id", ""))
    executor_supported = executor_id == SUPPORTED_EXECUTOR
    gates.append({"name": "candidate_status", "status": "pass" if candidate_status == SUPPORTED_CANDIDATE_STATUS else "fail", "expected": SUPPORTED_CANDIDATE_STATUS, "actual": candidate_status})
    gates.append({"name": "candidate_preview_only", "status": "pass" if candidate.get("files_changed") == 0 and candidate.get("apply_enabled") is False and candidate.get("live_path") is None else "fail"})
    gates.append({"name": "approval", "status": "pass" if approve == approval_id else "fail", "expected": approval_id, "actual": "provided" if approve else "missing"})

    target_label = None
    if live_target:
        raw_target_path = Path(live_target).expanduser()
        target_path = raw_target_path.resolve()
        target_under_home = is_under(target_path, home)
        target_label = safe_path_label(target_path, home)
        target_symlinked = raw_target_path.is_symlink() or _has_symlink_parent(raw_target_path, home)
    else:
        raw_target_path = None
        target_path = None
        target_under_home = False
        target_label = None
        target_symlinked = False
    gates.append({"name": "live_target_explicit", "status": "pass" if bool(live_target) else "fail"})
    gates.append({"name": "live_target_under_hermes_home", "status": "pass" if target_under_home else "fail"})
    gates.append({"name": "live_target_not_symlinked", "status": "pass" if live_target and not target_symlinked else "fail"})
    gates.append({"name": "executor_registered", "status": "pass" if executor_supported else "fail", "expected": SUPPORTED_EXECUTOR, "actual": executor_id or "missing"})
    gates.append({"name": "execute_requested", "status": "pass" if execute else "not_requested"})

    out_dir.mkdir(parents=True, exist_ok=True)
    core_gates_pass = all(g["status"] == "pass" for g in gates if g["name"] not in {"execute_requested", "executor_registered"})
    plan = {
        "schema_version": APPLY_PLAN_SCHEMA,
        "generated_at": _now(),
        "candidate": safe_path_label(candidate_file, home),
        "candidate_status": candidate_status,
        "approval_id": approval_id,
        "approval_matched": approve == approval_id,
        "executor_id": executor_id or None,
        "virtual_path": candidate.get("virtual_path"),
        "live_target": target_label,
        "live_target_required": True,
        "backup_required_before_executor": True,
        "backup_created": False,
        "gates": gates,
        "files_changed": 0,
        "apply_enabled": False,
    }

    if not core_gates_pass:
        status = "APPLY_BLOCKED_PRECHECK_FAILED"
        reason = "One or more apply prechecks failed; Forge stopped before any mutation."
    elif not executor_supported:
        status = "APPLY_BLOCKED_NO_EXECUTOR"
        reason = "No apply executor is registered for this candidate, so Forge stopped before any mutation."
    elif not execute:
        status = "APPLY_READY_EXECUTOR_AVAILABLE"
        reason = "A bounded executor is available, but --execute was not requested. Forge stopped before mutation."
    else:
        status = "APPLY_EXECUTION_PENDING"
        reason = "Prechecks passed; executing bounded frontmatter metadata patch."

    if status == "APPLY_BLOCKED_PRECHECK_FAILED":
        backup_status = "BACKUP_NOT_CREATED_PRECHECK_FAILED"
    elif status == "APPLY_BLOCKED_NO_EXECUTOR":
        backup_status = "BACKUP_NOT_CREATED_NO_EXECUTOR"
    else:
        backup_status = "BACKUP_NOT_CREATED_NOT_EXECUTED"
    backup_manifest = {
        "schema_version": BACKUP_MANIFEST_SCHEMA,
        "status": backup_status,
        "reason": "Backup is created only immediately before a registered executor mutates a live target.",
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
        "executor_id": executor_id or None,
        "backup_created": False,
    }

    if status == "APPLY_EXECUTION_PENDING":
        try:
            _preflight_artifact_paths(out_dir, ["apply-plan.json", "backup-manifest.json", "apply-result.json", "apply-plan.md", "backups/target-before.txt"])
            assert target_path is not None
            backup_manifest, result = _execute_skill_frontmatter_metadata(target_path=target_path, home=home, out_dir=out_dir, candidate=candidate, plan=plan)
        except (OSError, ValueError) as exc:
            result = {
                "schema_version": APPLY_RESULT_SCHEMA,
                "ok": False,
                "status": "APPLY_ARTIFACT_WRITE_BLOCKED" if "artifact" in str(exc) or "path escapes" in str(exc) else "APPLY_EXECUTION_BLOCKED",
                "reason": str(exc),
                "out": safe_path_label(out_dir, home),
                "files_changed": 0,
                "apply_enabled": False,
                "executor_ran": False,
                "executor_id": executor_id or None,
                "backup_created": False,
            }
            backup_manifest = {
                "schema_version": BACKUP_MANIFEST_SCHEMA,
                "status": "BACKUP_NOT_CREATED_EXECUTION_BLOCKED",
                "reason": str(exc),
                "live_target": target_label,
                "files_backed_up": 0,
            }

    return _write_apply_artifacts(out_dir, home, plan, backup_manifest, result)
