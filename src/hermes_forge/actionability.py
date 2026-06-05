from __future__ import annotations

import re

from hermes_forge.models import EvidenceItem

COUNT_RE = re.compile(r"(?:markers found|findings|cards)=?[: ]+(\d+)|cards=(\d+)")

TYPE_WEIGHTS = {
    "gateway_delivery_gap": 70,
    "profile_auth_or_provider_gap": 82,
    "repeated_tool_failure": 76,
    "doctor_report_signal": 68,
    "kanban_workflow_signal": 58,
    "stale_skill_instruction": 54,
    "cron_metadata_gap": 52,
    "session_history_signal": 45,
}

PRIORITY_LABELS = [(85, "critical"), (70, "high"), (50, "medium"), (0, "low")]

TEMPLATES = {
    "gateway_delivery_gap": {
        "hypothesis": "Gateway delivery shows repeated delivery/channel friction. The next useful work is to isolate whether this is stale message editing, platform delivery, or gateway state drift.",
        "next_checks": [
            "Review category counts by recent log window before reading raw logs.",
            "Compare gateway delivery findings with the active platform/gateway contract.",
            "If still relevant, run a focused gateway delivery smoke outside Forge; do not restart services from Forge.",
        ],
        "review_focus": "delivery reliability and stale message/edit handling",
    },
    "profile_auth_or_provider_gap": {
        "hypothesis": "Provider/auth/model markers repeat in runtime logs. This often points to provider configuration drift, model routing issues, or exhausted/invalid credentials, but Forge does not inspect secrets.",
        "next_checks": [
            "Run a secret-safe config/provider audit that checks key names and provider/model presence only.",
            "Compare findings with recent Hermes model/provider changes.",
            "Do not paste tokens into reports; validate credentials manually if needed.",
        ],
        "review_focus": "provider routing and auth-surface health without exposing secrets",
    },
    "repeated_tool_failure": {
        "hypothesis": "Tool/runtime failures repeat often enough to deserve a focused reproduction. The likely improvement is a better guard, clearer fallback, or targeted test around the failing tool path.",
        "next_checks": [
            "Group recent tool failures by tool/category before opening raw logs.",
            "Reproduce the top category with a bounded fixture or smoke command.",
            "Add a regression test or skill note only after the failure mode is confirmed.",
        ],
        "review_focus": "root-cause reproduction before patching",
    },
    "doctor_report_signal": {
        "hypothesis": "An existing Doctor report still has unresolved findings. Forge should use it as a prioritization source, not rerun or repair Doctor findings automatically.",
        "next_checks": [
            "Open the referenced Doctor report and rank unresolved findings by severity and recency.",
            "Cross-check whether the same theme appears in Forge logs/Kanban evidence.",
            "Create one manual repair/review card for the highest confirmed issue.",
        ],
        "review_focus": "correlating Doctor findings with runtime evidence",
    },
    "kanban_workflow_signal": {
        "hypothesis": "Kanban aggregate data shows workflow shape that may reveal blocked or non-standard task states. Forge does not copy card bodies, so this is a routing/process signal only.",
        "next_checks": [
            "Inspect status buckets in the Kanban UI or board report, not raw DB rows.",
            "Check whether custom/redacted statuses represent intentional workflow states or stale cards.",
            "If useful, add a team operating rule or cleanup proposal outside Forge.",
        ],
        "review_focus": "workflow hygiene and blocked/stale work detection",
    },
    "stale_skill_instruction": {
        "hypothesis": "A skill lacks basic metadata and may route/load poorly. The improvement is usually metadata/frontmatter cleanup, not behavioral rewrite.",
        "next_checks": [
            "Open the skill frontmatter only; verify name/description/version fields.",
            "Patch metadata with minimal wording and rerun Forge scan.",
            "Do not rewrite skill body unless a separate evidence item proves behavior drift.",
        ],
        "review_focus": "skill metadata quality",
    },
}

DEFAULT_TEMPLATE = {
    "hypothesis": "Forge found a weak signal, but the current evidence is not specific enough for a safe change. Treat this as a review candidate, not an implementation request.",
    "next_checks": [
        "Inspect the evidence category and source summary.",
        "Look for correlation with another evidence source before editing anything.",
        "If no correlation exists, keep this as watch-only.",
    ],
    "review_focus": "evidence quality before change",
}


def _count_hint(evidence: list[EvidenceItem]) -> int:
    total = 0
    for item in evidence:
        for match in COUNT_RE.finditer(item.fact):
            nums = [int(x) for x in match.groups() if x]
            total += sum(nums)
    return total


def priority_for(finding_type: str, evidence: list[EvidenceItem]) -> tuple[int, str, str]:
    base = TYPE_WEIGHTS.get(finding_type, 40)
    count = _count_hint(evidence)
    boost = 0
    if count >= 1000:
        boost = 18
    elif count >= 100:
        boost = 12
    elif count >= 10:
        boost = 6
    if any(item.source_type == "doctor_report" for item in evidence):
        boost += 8
    score = min(100, base + boost)
    label = next(label for threshold, label in PRIORITY_LABELS if score >= threshold)
    reason = f"Base={base}; count_hint={count}; boost={boost}; final={score}."
    return score, label, reason


def template_for(finding_type: str) -> dict[str, object]:
    return TEMPLATES.get(finding_type, DEFAULT_TEMPLATE)
