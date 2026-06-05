#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERNS = {
    "raw_user_path": re.compile(r"/Users/[^/\s]+"),
    "token_shape": re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{20,}\b|sk-[A-Za-z0-9_-]{16,}|github_pat_[A-Za-z0-9_]{16,}|ghp_[A-Za-z0-9_]{16,}"),
    "secret_assignment": re.compile(r"(?i)(api[_-]?key|token|secret|password|cookie)\s*[:=]\s*[^\s]+"),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}

SKIP_FILES = {
    "scripts/privacy_scan.py",
    "src/hermes_forge/redaction.py",
}

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "build", "dist"}


def should_skip(path: Path, root: Path) -> bool:
    if any(part in SKIP_DIRS or part.endswith(".egg-info") for part in path.parts):
        return True
    if root.is_dir():
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            rel = str(path)
        return rel in SKIP_FILES
    return False


def main() -> int:
    roots = [Path(a) for a in sys.argv[1:]] or [Path(".")]
    bad = []
    for root in roots:
        paths = [root] if root.is_file() else list(root.rglob("*"))
        for p in paths:
            if not p.is_file() or should_skip(p, root):
                continue
            data = p.read_bytes()
            if b"\0" in data[:4096]:
                continue
            text = data.decode("utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), 1):
                for kind, rx in PATTERNS.items():
                    if rx.search(line) and "[REDACTED" not in line and "TOKEN_SHAPE" not in line:
                        bad.append((kind, str(p), i, line[:160]))
    for item in bad[:100]:
        print(" | ".join(map(str, item)))
    print("findings:", len(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
