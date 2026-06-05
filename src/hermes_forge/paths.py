from __future__ import annotations

import os
from pathlib import Path


def resolve_hermes_home(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    if os.environ.get("HERMES_HOME"):
        return Path(os.environ["HERMES_HOME"]).expanduser().resolve()
    return (Path.home() / ".hermes").resolve()


def ensure_under(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError("path escapes allowed root")
    return resolved


def is_under(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    root_resolved = root.resolve()
    return resolved == root_resolved or root_resolved in resolved.parents


def write_text_under(path: Path, root: Path, text: str) -> None:
    if path.is_symlink():
        raise ValueError("refusing to overwrite symlink artifact")
    target = ensure_under(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        stat = target.stat()
        if getattr(stat, "st_nlink", 1) > 1:
            raise ValueError("refusing to overwrite hardlinked artifact")
    target.write_text(text, encoding="utf-8")
