from __future__ import annotations

import re
from pathlib import Path

from hermes_forge.models import EvidenceItem

CATEGORIES = {
    "profile_auth_or_provider_gap": re.compile(r"(?i)(auth|unauthorized|provider|model|rate.?limit)"),
    "gateway_delivery_gap": re.compile(r"(?i)(gateway|telegram|delivery|message to edit not found)"),
    "repeated_tool_failure": re.compile(r"(?i)(traceback|tool error|exception|failed tool)"),
}


def _tail(path: Path, max_bytes: int = 120_000) -> str:
    if path.is_symlink() or not path.is_file():
        return ""
    size = path.stat().st_size
    with path.open("rb") as f:
        if size > max_bytes:
            f.seek(max(0, size - max_bytes))
        return f.read(max_bytes).decode("utf-8", errors="ignore")


def collect_log_evidence(profile_path: Path, profile_name: str, start_id: int = 1) -> list[EvidenceItem]:
    logs_dir = profile_path / "logs"
    if not logs_dir.is_dir() or logs_dir.is_symlink():
        return []
    counts = {k: 0 for k in CATEGORIES}
    for log in sorted(logs_dir.glob("*.log"))[:20]:
        text = _tail(log)
        for line in text.splitlines()[-1000:]:
            for name, rx in CATEGORIES.items():
                if rx.search(line):
                    counts[name] += 1
                    break
    evidence = []
    idx = start_id
    for finding_type, count in counts.items():
        if count:
            evidence.append(EvidenceItem(id=f"ev-{idx:06d}", source_type="gateway_log", source_ref=f"profile:{profile_name}:logs", profile=profile_name, component="gateway", finding_type=finding_type, fact=f"Log category markers found: {count}", interpretation="Bounded logs contain repeated runtime markers. Raw lines were not stored.", severity="low", confidence="medium", suggested_targets=["eval_candidate", "routing_note"]))
            idx += 1
    return evidence
