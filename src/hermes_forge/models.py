from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EvidenceItem:
    id: str
    source_type: str
    source_ref: str
    profile: str
    component: str
    finding_type: str
    fact: str
    interpretation: str
    severity: str = "info"
    confidence: str = "medium"
    privacy: str = "profile-private"
    redacted: bool = True
    suggested_targets: list[str] = field(default_factory=list)
    schema_version: str = "hermes-forge.evidence/v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Finding:
    id: str
    type: str
    evidence_ids: list[str]
    root_cause_hypothesis: str
    severity: str
    confidence: str
    owner: str
    auto_apply_forbidden: bool
    next_action: str
    schema_version: str = "hermes-forge.finding/v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
