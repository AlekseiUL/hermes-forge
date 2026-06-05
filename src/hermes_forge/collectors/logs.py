from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from hermes_forge.models import EvidenceItem

CATEGORIES = {
    "profile_auth_or_provider_gap": re.compile(r"(?i)(auth|unauthorized|provider|model|rate.?limit)"),
    "gateway_delivery_gap": re.compile(r"(?i)(gateway|telegram|delivery|message to edit not found)"),
    "repeated_tool_failure": re.compile(r"(?i)(traceback|tool error|exception|failed tool)"),
}

GATEWAY_DELIVERY_TERMS = {
    "message_thread_id": re.compile(r"(?i)message_thread_id"),
    "thread": re.compile(r"(?i)thread"),
    "topic": re.compile(r"(?i)topic"),
    "chat_id": re.compile(r"(?i)chat_id"),
    "bad_request": re.compile(r"(?i)bad request|\b400\b"),
    "not_found": re.compile(r"(?i)not found"),
    "timeout": re.compile(r"(?i)timeout|timed out"),
    "forbidden": re.compile(r"(?i)forbidden|unauthorized|\b401\b|\b403\b"),
    "send_fail": re.compile(r"(?i)failed to send|send failed|send_message|sendMessage"),
}

GATEWAY_ERROR_CONTEXT = re.compile(r"(?i)(error|fail|exception|bad request|forbidden|timeout|not found|unauthorized|retry)")

TOOL_RUNTIME_CATEGORIES = {
    "tool_call_exception": re.compile(r"(?i)(tool.*exception|error executing tool|tool error|failed tool|function call.*error)"),
    "terminal_or_process": re.compile(r"(?i)(terminal|subprocess|process|command failed|exit code|non-zero|returncode)"),
    "browser_or_cdp": re.compile(r"(?i)(browser_|browser\.|playwright|cdp|chrome|devtools)"),
    "file_or_patch": re.compile(r"(?i)(read_file|write_file|patch|search_files|file not found|permission denied)"),
    "delegation": re.compile(r"(?i)(delegate_task|delegation|subagent|child agent)"),
    "cron_job": re.compile(r"(?i)(cron|scheduled job|job_id|scheduler)"),
    "json_schema_parse": re.compile(r"(?i)(json|schema|parse|invalid.*argument|validation|JSONDecodeError|ValidationError)"),
    "network_http": re.compile(r"(?i)(http|timeout|connection|network|\b502\b|\b503\b|\b504\b|\b429\b|rate.?limit)"),
    "mcp_tool": re.compile(r"(?i)\bmcp\b"),
    "python_traceback": re.compile(r"(?i)(traceback|exception|stack trace)"),
}

TOOL_NAME_PATTERNS = [
    re.compile(r"(?i)tool[_ ](?:name|call)?[=: ]+([a-zA-Z_][\w.-]{1,60})"),
    re.compile(r"(?i)(?:calling|execute|executing) tool[: ]+([a-zA-Z_][\w.-]{1,60})"),
    re.compile(r"(?i)function[=: ]+([a-zA-Z_][\w.-]{1,60})"),
]

EXCEPTION_CLASS = re.compile(r"^\s*([A-Z][A-Za-z0-9_]*(?:Error|Exception|Timeout|Warning))\b")
EXIT_CODE = re.compile(r"(?i)(?:exit code|exit_code|returncode|returned non-zero exit status)\D+(\d{1,3})")
SAFE_TOOL_LABEL = re.compile(r"^[a-zA-Z_][\w.-]{1,60}$")
UNSAFE_TOOL_LABELS = {"arg", "args", "argument", "arguments", "function", "tool", "tools", "call", "calls"}

EXIT_CONTEXT_KEYWORDS = {
    "git": re.compile(r"(?i)\bgit\b|github|repo|commit|push|pull|fetch"),
    "shell": re.compile(r"(?i)shell|terminal|command|subprocess|bash|zsh"),
    "python": re.compile(r"(?i)python|pytest|pip|venv"),
    "network": re.compile(r"(?i)http|network|timeout|connection|ssl|dns"),
    "file": re.compile(r"(?i)file|path|permission|not found|directory"),
    "auth": re.compile(r"(?i)auth|token|credential|permission denied|forbidden|unauthorized"),
    "kanban": re.compile(r"(?i)kanban|card|board"),
    "cron": re.compile(r"(?i)cron|job|schedule"),
}


def _tail(path: Path, max_bytes: int = 120_000) -> str:
    if path.is_symlink() or not path.is_file():
        return ""
    size = path.stat().st_size
    with path.open("rb") as f:
        if size > max_bytes:
            f.seek(max(0, size - max_bytes))
        return f.read(max_bytes).decode("utf-8", errors="ignore")


def _as_plain_counts(counter: Counter[str], limit: int | None = None) -> dict[str, int]:
    items = counter.most_common(limit) if limit else sorted(counter.items())
    return {str(k): int(v) for k, v in items if v}


def _join_counts(counts: dict[str, int], *, limit: int = 8) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit])


def classify_gateway_delivery_lines(lines: Iterable[str], recent_window: int = 1000) -> dict[str, dict[str, int]]:
    """Classify gateway delivery markers using safe counts only.

    The broad term counts are informational. `terms_error_context` is the
    actionable layer because normal Telegram events can contain thread/topic
    fields without representing a delivery failure.
    """
    rows = list(lines)
    recent_start = max(0, len(rows) - recent_window)
    terms_total: Counter[str] = Counter()
    terms_error_context: Counter[str] = Counter()
    terms_recent: Counter[str] = Counter()
    terms_recent_error_context: Counter[str] = Counter()

    for idx, line in enumerate(rows):
        has_error_context = bool(GATEWAY_ERROR_CONTEXT.search(line))
        is_recent = idx >= recent_start
        for term, pattern in GATEWAY_DELIVERY_TERMS.items():
            if not pattern.search(line):
                continue
            terms_total[term] += 1
            if has_error_context:
                terms_error_context[term] += 1
            if is_recent:
                terms_recent[term] += 1
                if has_error_context:
                    terms_recent_error_context[term] += 1

    return {
        "terms_total": _as_plain_counts(terms_total),
        "terms_error_context": _as_plain_counts(terms_error_context),
        "terms_recent": _as_plain_counts(terms_recent),
        "terms_recent_error_context": _as_plain_counts(terms_recent_error_context),
    }


def classify_tool_runtime_lines(lines: Iterable[str], recent_window: int = 1000) -> dict[str, dict[str, int]]:
    """Classify tool/runtime failure markers using safe attribution only.

    This function intentionally does not return raw lines, raw commands,
    arguments, paths, chat IDs, or exception messages. If a tool label is not
    explicit and safely shaped, it reports `unknown/no_explicit_tool_label`
    instead of guessing.
    """
    rows = list(lines)
    recent_start = max(0, len(rows) - recent_window)
    categories: Counter[str] = Counter()
    categories_recent: Counter[str] = Counter()
    exception_classes: Counter[str] = Counter()
    exception_classes_recent: Counter[str] = Counter()
    exit_codes: Counter[str] = Counter()
    exit_codes_recent: Counter[str] = Counter()
    tool_labels: Counter[str] = Counter()
    tool_labels_recent: Counter[str] = Counter()
    exit_context: dict[str, Counter[str]] = defaultdict(Counter)

    for idx, line in enumerate(rows):
        is_recent = idx >= recent_start
        matched_category = False
        for category, pattern in TOOL_RUNTIME_CATEGORIES.items():
            if pattern.search(line):
                categories[category] += 1
                matched_category = True
                if is_recent:
                    categories_recent[category] += 1

        exc = EXCEPTION_CLASS.search(line)
        if exc:
            name = exc.group(1)
            exception_classes[name] += 1
            if is_recent:
                exception_classes_recent[name] += 1

        exit_match = EXIT_CODE.search(line)
        if exit_match:
            code = exit_match.group(1)
            exit_codes[code] += 1
            if is_recent:
                exit_codes_recent[code] += 1
            window = "\n".join(rows[max(0, idx - 2): min(len(rows), idx + 3)])
            any_keyword = False
            for keyword, pattern in EXIT_CONTEXT_KEYWORDS.items():
                if pattern.search(window):
                    exit_context[code][keyword] += 1
                    any_keyword = True
            if not any_keyword:
                exit_context[code]["unclassified"] += 1

        explicit_tool = None
        for pattern in TOOL_NAME_PATTERNS:
            match = pattern.search(line)
            if match and SAFE_TOOL_LABEL.match(match.group(1)):
                candidate = match.group(1)
                if candidate.lower() not in UNSAFE_TOOL_LABELS:
                    explicit_tool = candidate
                    break
        if explicit_tool:
            tool_labels[explicit_tool] += 1
            if is_recent:
                tool_labels_recent[explicit_tool] += 1
        elif matched_category:
            tool_labels["unknown/no_explicit_tool_label"] += 1
            if is_recent:
                tool_labels_recent["unknown/no_explicit_tool_label"] += 1

    return {
        "categories": _as_plain_counts(categories),
        "categories_recent": _as_plain_counts(categories_recent),
        "exception_classes": _as_plain_counts(exception_classes, limit=20),
        "exception_classes_recent": _as_plain_counts(exception_classes_recent, limit=20),
        "exit_codes": _as_plain_counts(exit_codes, limit=20),
        "exit_codes_recent": _as_plain_counts(exit_codes_recent, limit=20),
        "tool_labels": _as_plain_counts(tool_labels, limit=20),
        "tool_labels_recent": _as_plain_counts(tool_labels_recent, limit=20),
        "exit_context_keywords": {code: _as_plain_counts(counter, limit=12) for code, counter in sorted(exit_context.items())},
    }


def collect_log_evidence(profile_path: Path, profile_name: str, start_id: int = 1) -> list[EvidenceItem]:
    logs_dir = profile_path / "logs"
    if not logs_dir.is_dir() or logs_dir.is_symlink():
        return []
    counts = {k: 0 for k in CATEGORIES}
    gateway_error_terms: Counter[str] = Counter()
    gateway_recent_error_terms: Counter[str] = Counter()
    tool_categories: Counter[str] = Counter()
    tool_recent_categories: Counter[str] = Counter()
    tool_exit_codes: Counter[str] = Counter()
    tool_exception_classes: Counter[str] = Counter()
    tool_labels: Counter[str] = Counter()

    for log in sorted(logs_dir.glob("*.log"))[:20]:
        text = _tail(log)
        lines = text.splitlines()[-1000:]
        for line in lines:
            for name, rx in CATEGORIES.items():
                if rx.search(line):
                    counts[name] += 1
                    break

        gateway = classify_gateway_delivery_lines(lines)
        gateway_error_terms.update(gateway["terms_error_context"])
        gateway_recent_error_terms.update(gateway["terms_recent_error_context"])

        tool = classify_tool_runtime_lines(lines)
        tool_categories.update(tool["categories"])
        tool_recent_categories.update(tool["categories_recent"])
        tool_exit_codes.update(tool["exit_codes"])
        tool_exception_classes.update(tool["exception_classes"])
        tool_labels.update(tool["tool_labels"])

    evidence = []
    idx = start_id
    for finding_type, count in counts.items():
        if count:
            evidence.append(EvidenceItem(id=f"ev-{idx:06d}", source_type="gateway_log", source_ref=f"profile:{profile_name}:logs", profile=profile_name, component="gateway", finding_type=finding_type, fact=f"Log category markers found: {count}", interpretation="Bounded logs contain repeated runtime markers. Raw lines were not stored.", severity="low", confidence="medium", suggested_targets=["eval_candidate", "routing_note"]))
            idx += 1

    if gateway_error_terms:
        evidence.append(EvidenceItem(
            id=f"ev-{idx:06d}",
            source_type="gateway_log_classifier",
            source_ref=f"profile:{profile_name}:logs:gateway_delivery_classifier",
            profile=profile_name,
            component="gateway",
            finding_type="gateway_delivery_gap",
            fact=f"Gateway delivery error-context terms: {_join_counts(dict(gateway_error_terms))}; recent: {_join_counts(dict(gateway_recent_error_terms))}",
            interpretation="Strict classifier stores counts only. Broad thread/topic markers are not treated as actionable unless they occur in error context.",
            severity="low",
            confidence="medium",
            suggested_targets=["eval_candidate", "routing_note"],
        ))
        idx += 1

    if tool_categories or tool_exit_codes or tool_exception_classes:
        evidence.append(EvidenceItem(
            id=f"ev-{idx:06d}",
            source_type="tool_runtime_classifier",
            source_ref=f"profile:{profile_name}:logs:tool_runtime_classifier",
            profile=profile_name,
            component="runtime",
            finding_type="repeated_tool_failure",
            fact=(
                f"Tool/runtime categories: {_join_counts(dict(tool_categories))}; "
                f"recent: {_join_counts(dict(tool_recent_categories))}; "
                f"exit_codes: {_join_counts(dict(tool_exit_codes))}; "
                f"exceptions: {_join_counts(dict(tool_exception_classes))}; "
                f"tool_labels: {_join_counts(dict(tool_labels))}"
            ),
            interpretation="Classifier stores safe attribution counts only. Missing explicit tool names are reported as unknown/no_explicit_tool_label instead of guessed.",
            severity="low",
            confidence="medium",
            suggested_targets=["eval_candidate", "routing_note"],
        ))
    return evidence
