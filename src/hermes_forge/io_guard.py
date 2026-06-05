from __future__ import annotations

from pathlib import Path


def snapshot_tree(root: Path) -> dict[str, tuple[int, int]]:
    if not root.exists():
        return {}
    snap = {}
    for p in root.rglob("*"):
        if p.is_symlink() or not p.is_file():
            continue
        st = p.stat()
        snap[str(p.relative_to(root))] = (st.st_size, int(st.st_mtime_ns))
    return snap
