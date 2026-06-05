from __future__ import annotations

import json
from pathlib import Path

from hermes_forge.models import EvidenceItem
from hermes_forge.redaction import safe_path_label


def collect_cron_evidence(profile_path: Path, profile_name: str, hermes_home: Path, start_id: int = 1) -> list[EvidenceItem]:
    jobs_file = profile_path / "cron" / "jobs.json"
    if not jobs_file.is_file() or jobs_file.is_symlink():
        return []
    try:
        data = json.loads(jobs_file.read_text(encoding="utf-8"))
    except Exception as exc:
        return [EvidenceItem(id=f"ev-{start_id:06d}", source_type="cron", source_ref=safe_path_label(jobs_file, hermes_home), profile=profile_name, component="cron", finding_type="cron_noise_or_failure", fact=f"cron jobs.json unreadable: {type(exc).__name__}", interpretation="Cron metadata cannot be trusted.", severity="medium", confidence="high", suggested_targets=["cron_prompt_fix_candidate"])]
    evidence = []
    idx = start_id
    for job in data.get("jobs", []):
        if not isinstance(job, dict):
            continue
        if job.get("last_error") or job.get("last_delivery_error") or str(job.get("last_status") or "").lower() not in {"", "ok", "success", "none"}:
            evidence.append(EvidenceItem(id=f"ev-{idx:06d}", source_type="cron", source_ref=f"profile:{profile_name}:cron:{job.get('id','unknown')}", profile=profile_name, component="cron", finding_type="cron_noise_or_failure", fact="Cron job has non-green status or stored error metadata.", interpretation="Scheduled automation may be silently failing.", severity="medium", confidence="medium", suggested_targets=["cron_prompt_fix_candidate", "eval_candidate"]))
            idx += 1
    return evidence
