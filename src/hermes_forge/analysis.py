from __future__ import annotations

from collections import defaultdict

from hermes_forge.actionability import priority_for, template_for
from hermes_forge.models import EvidenceItem, Finding


def analyze_evidence(items: list[EvidenceItem]) -> list[Finding]:
    groups: dict[tuple[str, str], list[EvidenceItem]] = defaultdict(list)
    for item in items:
        groups[(item.profile, item.finding_type)].append(item)
    findings = []
    for idx, ((profile, finding_type), evidence) in enumerate(sorted(groups.items()), 1):
        score, label, reason = priority_for(finding_type, evidence)
        sev = "high" if score >= 70 else "medium" if score >= 50 else "low"
        tpl = template_for(finding_type)
        next_checks = list(tpl["next_checks"])
        findings.append(Finding(
            id=f"find-{idx:06d}",
            type=finding_type,
            evidence_ids=[e.id for e in evidence],
            root_cause_hypothesis=str(tpl["hypothesis"]),
            severity=sev,
            confidence="medium",
            owner=profile,
            auto_apply_forbidden=True,
            next_action=next_checks[0] if next_checks else "Review evidence before applying any change.",
            priority_score=score,
            priority_label=label,
            priority_reason=reason,
            review_focus=str(tpl["review_focus"]),
            next_checks=next_checks,
        ))
    return sorted(findings, key=lambda f: (-f.priority_score, f.type, f.owner))
