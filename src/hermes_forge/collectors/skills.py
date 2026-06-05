from __future__ import annotations

from pathlib import Path

from hermes_forge.models import EvidenceItem
from hermes_forge.redaction import safe_path_label


def _frontmatter_keys(path: Path, max_bytes: int = 8192) -> set[str]:
    if path.is_symlink() or not path.is_file():
        return set()
    text = path.open("rb").read(max_bytes).decode("utf-8", errors="ignore")
    if not text.startswith("---"):
        return set()
    end = text.find("\n---", 3)
    if end < 0:
        return set()
    keys = set()
    for line in text[3:end].splitlines():
        if ":" in line and not line.startswith(" "):
            keys.add(line.split(":", 1)[0].strip())
    return keys


def collect_skill_evidence(profile_path: Path, profile_name: str, hermes_home: Path, start_id: int = 1) -> list[EvidenceItem]:
    skills_dir = profile_path / "skills"
    evidence = []
    if not skills_dir.is_dir() or skills_dir.is_symlink():
        return evidence
    idx = start_id
    for skill in sorted(skills_dir.rglob("SKILL.md")):
        if skill.is_symlink():
            continue
        keys = _frontmatter_keys(skill)
        missing = sorted({"name", "description"} - keys)
        if missing:
            evidence.append(EvidenceItem(
                id=f"ev-{idx:06d}", source_type="skill", source_ref=safe_path_label(skill, hermes_home), profile=profile_name, component="skill",
                finding_type="stale_skill_instruction", fact=f"Skill metadata missing keys: {', '.join(missing)}",
                interpretation="Skill may route or load poorly without basic frontmatter.", severity="low", confidence="high", suggested_targets=["skill_patch_candidate", "eval_candidate"]
            ))
            idx += 1
    return evidence
