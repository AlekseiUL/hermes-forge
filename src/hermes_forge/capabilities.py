from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import Any

from hermes_forge import __version__
from hermes_forge.redaction import safe_path_label

CAPABILITIES_SCHEMA = "hermes-forge.capabilities/v1"
DOCTOR_SCHEMA = "hermes-forge.doctor/v1"

READ_ONLY_ADAPTERS = {
    "profiles": {"status": "available", "mode": "metadata_only", "required": True},
    "skills": {"status": "available", "mode": "frontmatter_metadata_only", "required": False},
    "cron": {"status": "available", "mode": "metadata_only", "required": False},
    "logs": {"status": "available", "mode": "category_counts_only", "required": False},
    "sessions": {"status": "available", "mode": "sqlite_metadata_only", "required": False},
    "kanban": {"status": "optional_path", "mode": "aggregate_metadata_only", "required": False},
    "doctor_report": {"status": "optional_path", "mode": "safe_summary_only", "required": False},
}

SIDE_EFFECTS = {
    "edits_hermes_home": False,
    "executes_cron": False,
    "executes_plugins": False,
    "executes_mcp_servers": False,
    "restarts_gateway": False,
    "sends_platform_messages": False,
    "pushes_to_github": False,
    "network_required": False,
    "apply_enabled": False,
}


def build_capabilities() -> dict[str, Any]:
    return {
        "schema_version": CAPABILITIES_SCHEMA,
        "package": "hermes-forge",
        "version": __version__,
        "mvp_boundary": "read-only scan/analyze/propose/eval; apply disabled",
        "apply_supported": False,
        "apply_status": "APPLY_DISABLED_IN_MVP",
        "adapters": READ_ONLY_ADAPTERS,
        "side_effects": SIDE_EFFECTS,
        "artifact_classes": {
            "local_private": ["raw scan output", "evidence ledger", "generated proposals"],
            "shareable_after_review": ["redacted proposal.md", "eval-plan.md", "scan-summary.json"],
        },
    }


def run_doctor() -> dict[str, Any]:
    capabilities = build_capabilities()
    checks = [
        {"id": "python.version", "status": "OK", "detail": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"},
        {"id": "platform", "status": "OK", "detail": platform.system() or "unknown"},
        {"id": "apply.disabled", "status": "OK", "detail": capabilities["apply_status"]},
        {"id": "side_effects.disabled", "status": "OK", "detail": "no mutation/network/platform side effects in self-check"},
        {"id": "package.import", "status": "OK", "detail": "hermes_forge importable"},
    ]
    return {
        "schema_version": DOCTOR_SCHEMA,
        "ok": True,
        "status": "OK",
        "package": "hermes-forge",
        "version": __version__,
        "cwd_label": safe_path_label(Path.cwd()),
        "capabilities_schema": CAPABILITIES_SCHEMA,
        "checks": checks,
        "apply_enabled": False,
        "notes": [
            "Doctor is a Forge self-check only.",
            "It does not inspect secrets, execute Hermes services, or mutate Hermes homes.",
        ],
    }


def dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
