from __future__ import annotations
from pathlib import Path

from hermes_forge.redaction import safe_path_label


def discover_profiles(hermes_home: Path, all_profiles: bool = False, profile: str | None = None) -> dict:
    profiles = []
    if profile:
        candidates = [hermes_home if profile == "default" else hermes_home / "profiles" / profile]
    elif all_profiles:
        profiles_root = hermes_home / "profiles"
        candidates = [hermes_home]
        if profiles_root.is_dir():
            candidates.extend(sorted([p for p in profiles_root.iterdir()]))
    else:
        candidates = [hermes_home]
    for p in candidates:
        if p.is_symlink():
            profiles.append({"name": p.name, "path": safe_path_label(p, hermes_home), "status": "skipped_symlink"})
            continue
        profiles.append({"name": p.name if p != hermes_home else "default", "path": safe_path_label(p, hermes_home), "exists": p.exists(), "is_dir": p.is_dir()})
    return {"schema_version": "hermes-forge.inventory/v1", "hermes_home": safe_path_label(hermes_home, hermes_home), "profiles": profiles}
