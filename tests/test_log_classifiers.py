from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from hermes_forge.collectors.logs import (
    classify_gateway_delivery_lines,
    classify_tool_runtime_lines,
    collect_log_evidence,
)


def run(args, cwd: Path):
    env = {**os.environ, "PYTHONPATH": str(cwd / "src")}
    return subprocess.run([sys.executable, "-m", "hermes_forge.cli", *args], cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def artifact_text(out: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in sorted(out.rglob("*")) if path.is_file())


def fake_gh_value() -> str:
    return "ghp_" + "A" * 20


def fake_sk_value() -> str:
    return "sk-" + "B" * 20


def fake_user_path() -> str:
    return "/" + "Users" + "/private/project"


def test_gateway_delivery_classifier_separates_thread_noise_from_error_context():
    lines = [
        "normal Telegram update thread_id=12345 chat_id=-1001234567890",
        "normal Telegram update thread_id=12345 chat_id=-1001234567890",
        "ERROR failed to send message in thread message_thread_id=777 timeout",
        "message not found while retrying topic delivery",
    ]

    result = classify_gateway_delivery_lines(lines)

    assert result["terms_total"]["thread"] == 3
    assert result["terms_error_context"]["thread"] == 1
    assert result["terms_error_context"]["message_thread_id"] == 1
    assert result["terms_error_context"]["timeout"] == 1
    assert result["terms_error_context"]["not_found"] == 1


def test_tool_runtime_classifier_uses_safe_attribution_and_unknown_label():
    gh_value = fake_gh_value()
    user_path = fake_user_path()
    lines = [
        f"Executing tool: terminal args={{'command':'git fetch https://cred-{gh_value}@example.invalid/private'}}",
        "subprocess returned non-zero exit status 128 from git command",
        f"RuntimeError: private command failed at {user_path}",
        "Traceback (most recent call last):",
        "JSONDecodeError: token sk-sec...cret was bad",
        "function: arguments payload omitted",
        "tool error without explicit label",
    ]

    result = classify_tool_runtime_lines(lines)

    assert result["tool_labels"]["terminal"] == 1
    assert result["tool_labels"]["unknown/no_explicit_tool_label"] >= 1
    assert "arguments" not in result["tool_labels"]
    assert result["exit_codes"]["128"] == 1
    assert result["exception_classes"]["RuntimeError"] == 1
    assert result["exception_classes"]["JSONDecodeError"] == 1
    assert result["exit_context_keywords"]["128"]["git"] >= 1
    assert result["exit_context_keywords"]["128"]["shell"] >= 1

    serialized = json.dumps(result, ensure_ascii=False)
    assert gh_value not in serialized
    assert "sk-secret" not in serialized
    assert user_path not in serialized
    assert "private command failed" not in serialized


def test_collect_log_evidence_does_not_emit_raw_lines_args_or_tokens(tmp_path: Path):
    gh_value = fake_gh_value()
    sk_value = fake_sk_value()
    user_path = fake_user_path()
    profile = tmp_path / "profile"
    logs = profile / "logs"
    logs.mkdir(parents=True)
    (logs / "gateway.error.log").write_text(
        "\n".join([
            "normal update thread_id=123 chat_id=-100999",
            f"ERROR failed to send message in thread message_thread_id=777 timeout cred-{sk_value}",
            f"Executing tool: terminal args={{'command':'git fetch https://{gh_value}@example.invalid/private'}}",
            "subprocess returned non-zero exit status 128 from git command",
            f"RuntimeError: private command failed at {user_path}",
        ]),
        encoding="utf-8",
    )

    evidence = collect_log_evidence(profile, "operator")
    text = "\n".join(json.dumps(item.to_dict(), ensure_ascii=False) for item in evidence)

    assert "gateway_delivery_classifier" in text
    assert "tool_runtime_classifier" in text
    assert "message_thread_id=777" not in text
    assert "chat_id=-100999" not in text
    assert gh_value not in text
    assert sk_value not in text
    assert "git fetch" not in text
    assert user_path not in text
    assert "private command failed" not in text
    assert "unknown/no_explicit_tool_label" in text
    assert "exit_codes:" in text


def test_scan_outputs_safe_classifier_evidence_without_raw_log_content(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    gh_value = fake_gh_value()
    sk_value = fake_sk_value()
    user_path = fake_user_path()
    home = tmp_path / "home"
    profile_logs = home / "profiles" / "operator" / "logs"
    profile_logs.mkdir(parents=True)
    (profile_logs / "gateway.error.log").write_text(
        "\n".join([
            f"ERROR failed to send message in thread message_thread_id=777 timeout cred-{sk_value}",
            f"Executing tool: terminal args={{'command':'git fetch https://{gh_value}@example.invalid/private'}}",
            "subprocess returned non-zero exit status 128 from git command",
            f"RuntimeError: private command failed at {user_path}",
        ]),
        encoding="utf-8",
    )

    out = tmp_path / "forge"
    result = run(["scan", "--hermes-home", str(home), "--all-profiles", "--out", str(out)], repo)
    assert result.returncode == 0, result.stdout
    text = artifact_text(out)

    assert "gateway_log_classifier" in text
    assert "tool_runtime_classifier" in text
    assert "message_thread_id=777" not in text
    assert gh_value not in text
    assert sk_value not in text
    assert "git fetch" not in text
    assert user_path not in text
    assert "private command failed" not in text
