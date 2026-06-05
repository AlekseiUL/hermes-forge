from __future__ import annotations

from collections import defaultdict

from hermes_forge.models import EvidenceItem, Finding


def analyze_evidence(items: list[EvidenceItem]) -> list[Finding]:
    groups: dict[tuple[str, str], list[EvidenceItem]] = defaultdict(list)
    for item in items:
        groups[(item.profile, item.finding_type)].append(item)
    findings = []
    for idx, ((profile, finding_type), evidence) in enumerate(sorted(groups.items()), 1):
        sev = "medium" if any(e.severity in {"medium", "high", "blocker"} for e in evidence) else "low"
        findings.append(Finding(id=f"find-{idx:06d}", type=finding_type, evidence_ids=[e.id for e in evidence], root_cause_hypothesis=f"{finding_type} observed for profile {profile}", severity=sev, confidence="medium", owner=profile, auto_apply_forbidden=True, next_action="Generate reviewable proposal and eval plan; do not apply automatically."))
    return findings
