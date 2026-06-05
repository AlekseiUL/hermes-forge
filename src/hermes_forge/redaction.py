from __future__ import annotations

import re
from pathlib import Path
from typing import Any

TOKEN_PATTERNS = [
    re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{16,}"),
    re.compile(r"(?i)authorization:\s*bearer\s+[^\s]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
]
SECRET_ASSIGNMENT = re.compile(r"(?i)(api[_-]?key|token|secret|password|cookie)\s*[:=]\s*[^\s]+")
USER_PATH = re.compile(r"/Users/[^/\s]+")


def redact_text(text: str) -> str:
    out = text or ""
    for pattern in TOKEN_PATTERNS:
        out = pattern.sub("[REDACTED]", out)
    out = SECRET_ASSIGNMENT.sub(lambda m: f"{m.group(1)}=[REDACTED]", out)
    out = USER_PATH.sub("[REDACTED_PATH]", out)
    return out


def safe_path_label(path: str | Path, hermes_home: str | Path | None = None) -> str:
    p = Path(path)
    text = str(p)
    if hermes_home:
        home = str(Path(hermes_home))
        if text == home:
            return "<hermes-home>"
        if text.startswith(home + "/"):
            return "<hermes-home>" + text[len(home):]
    return USER_PATH.sub("[REDACTED_PATH]", text)


def redact_json(obj: Any) -> Any:
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, Path):
        return safe_path_label(obj)
    if isinstance(obj, list):
        return [redact_json(x) for x in obj]
    if isinstance(obj, dict):
        clean = {}
        for k, v in obj.items():
            key = str(k)
            if re.search(r"(?i)(token|secret|password|cookie|authorization)", key):
                clean[key] = "[REDACTED]"
            else:
                clean[key] = redact_json(v)
        return clean
    return obj
