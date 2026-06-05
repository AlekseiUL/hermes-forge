from __future__ import annotations

import json
from pathlib import Path

from hermes_forge.models import EvidenceItem
from hermes_forge.redaction import redact_text, safe_path_label


def _has_symlink_component(path: Path) -> bool:
    absolute = path.expanduser().absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.is_symlink():
            return True
    return False


def collect_doctor_report_evidence(report_path: Path | None, hermes_home: Path, start_id: int = 1) -> list[EvidenceItem]:
    if report_path is None:
        return []
    candidate = report_path.expanduser()
    if candidate.is_symlink() or _has_symlink_component(candidate) or not candidate.is_file():
        return [EvidenceItem(
            id=f"ev-{start_id:06d}", source_type="doctor_report", source_ref=safe_path_label(candidate, hermes_home), profile="external",
            component="doctor", finding_type="doctor_report_unavailable", fact="Doctor report path is not a regular file; import skipped.",
            interpretation="Forge imports existing reports only and never executes doctor commands.", severity="low", confidence="high", privacy="shareable-aggregate",
            suggested_targets=["collector_safety"],
        )]
    resolved = candidate.resolve()
    try:
        raw = resolved.read_text(encoding="utf-8", errors="ignore")[:65536]
    except OSError:
        raw = ""
    status = "unknown"
    finding_count = 0
    if resolved.suffix.lower() == ".json":
        try:
            data = json.loads(raw)
            status = str(data.get("status") or data.get("overall_status") or data.get("ok") or "unknown")
            findings = data.get("findings")
            if isinstance(findings, list):
                finding_count = len(findings)
            elif isinstance(data.get("summary"), dict):
                finding_count = int(data["summary"].get("findings", 0) or 0)
        except (json.JSONDecodeError, TypeError, ValueError):
            status = "unparseable_json"
    else:
        lowered = raw.lower()
        for marker in ("blocker", "major", "minor", "warn", "ok"):
            if marker in lowered:
                status = marker.upper()
                break
        finding_count = sum(1 for line in raw.splitlines() if line.lstrip().startswith(("- ", "* ")) and ("finding" in line.lower() or "status" in line.lower()))
    status = redact_text(status)[:80]
    return [EvidenceItem(
        id=f"ev-{start_id:06d}", source_type="doctor_report", source_ref=safe_path_label(resolved, hermes_home), profile="external",
        component="doctor", finding_type="doctor_report_signal", fact=f"Imported doctor report summary: status={status}, findings={finding_count}.",
        interpretation="Existing diagnostic reports can seed improvement proposals without executing diagnostics or copying raw report bodies.", severity="low", confidence="medium", privacy="shareable-aggregate",
        suggested_targets=["doctor_eval_candidate", "proposal_evidence"],
    )]
