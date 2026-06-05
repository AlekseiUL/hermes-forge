from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from hermes_forge.io_guard import snapshot_tree


def run(args, cwd: Path):
    env = {**os.environ, "PYTHONPATH": str(cwd / "src")}
    return subprocess.run([sys.executable, "-m", "hermes_forge.cli", *args], cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def read_all(out: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in sorted(out.rglob("*")) if path.is_file())


def test_improve_read_only_loop_writes_universal_artifacts_and_no_input_changes(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    kanban = repo / "tests" / "fixtures" / "kanban" / "kanban.db"
    doctor = repo / "tests" / "fixtures" / "doctor" / "report.json"
    before = snapshot_tree(fixture)
    out = tmp_path / "improve"

    p = run([
        "improve",
        "--mode", "read-only",
        "--hermes-home", str(fixture),
        "--all-profiles",
        "--kanban-db", str(kanban),
        "--doctor-report", str(doctor),
        "--out", str(out),
    ], repo)

    assert p.returncode == 0, p.stdout
    assert snapshot_tree(fixture) == before
    for name in [
        "run.json",
        "policy.json",
        "inventory.json",
        "evidence-ledger.jsonl",
        "findings.json",
        "dedup-groups.json",
        "opportunities.json",
        "proposals.json",
        "scan-summary.json",
        "redaction-report.json",
        "report.md",
    ]:
        assert (out / name).exists(), name

    run_json = json.loads((out / "run.json").read_text())
    assert run_json["mode"] == "read-only"
    assert run_json["apply_enabled"] is False
    assert run_json["files_changed"] == 0

    opportunities = json.loads((out / "opportunities.json").read_text())["opportunities"]
    assert opportunities
    assert {"owner_role", "reviewer_role", "implementer_role", "approver_role"}.issubset(opportunities[0])
    assert "Mike" not in json.dumps(opportunities, ensure_ascii=False)
    assert "Nacho" not in json.dumps(opportunities, ensure_ascii=False)
    assert "Walter" not in json.dumps(opportunities, ensure_ascii=False)

    report = (out / "report.md").read_text()
    assert "improvement opportunities, not just failures" in report
    assert "## Suggested experiments / evals" in report
    assert "files_changed: `0`" in report
    assert "did not apply patches" in report
    assert "Mike" not in report
    assert "Nacho" not in report
    assert "Walter" not in report


def test_improve_output_blocks_writing_under_scanned_home(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    out = fixture / "bad-out"

    p = run(["improve", "--mode", "read-only", "--hermes-home", str(fixture), "--out", str(out)], repo)

    assert p.returncode == 2
    assert "OUT_UNDER_HERMES_HOME_BLOCKED" in p.stdout
    assert not out.exists()


def test_improve_top_must_be_positive(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    out = tmp_path / "improve"

    p = run(["improve", "--mode", "read-only", "--hermes-home", str(fixture), "--top", "0", "--out", str(out)], repo)

    assert p.returncode == 2
    assert "INVALID_TOP" in p.stdout
    assert not out.exists()


def test_improve_top_limits_rendered_opportunities_not_total(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    out = tmp_path / "improve"

    p = run(["improve", "--mode", "read-only", "--hermes-home", str(fixture), "--all-profiles", "--top", "1", "--out", str(out)], repo)

    assert p.returncode == 0, p.stdout
    report = (out / "report.md").read_text()
    run_json = json.loads((out / "run.json").read_text())
    assert f"opportunities_total: `{run_json['opportunities']}`" in report
    assert "opportunities_shown: `1`" in report
    assert report.count("### opp-") == 1


def test_improve_report_does_not_emit_raw_lines_args_or_token_shapes(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    profile_logs = home / "profiles" / "operator" / "logs"
    profile_logs.mkdir(parents=True)
    gh_value = "ghp_" + "A" * 20
    sk_value = "sk-" + "B" * 20
    user_path = "/" + "Users" + "/private/project"
    (profile_logs / "gateway.error.log").write_text(
        "\n".join([
            f"ERROR failed to send message in thread message_thread_id=777 timeout cred-{sk_value}",
            f"Executing tool: terminal args={{'command':'git fetch https://{gh_value}@example.invalid/private'}}",
            "subprocess returned non-zero exit status 128 from git command",
            f"RuntimeError: private command failed at {user_path}",
        ]),
        encoding="utf-8",
    )
    out = tmp_path / "improve"

    p = run(["improve", "--mode", "read-only", "--hermes-home", str(home), "--all-profiles", "--out", str(out)], repo)

    assert p.returncode == 0, p.stdout
    text = read_all(out)
    assert "message_thread_id=777" not in text
    assert gh_value not in text
    assert sk_value not in text
    assert "git fetch" not in text
    assert user_path not in text
    assert "private command failed" not in text
    assert "unknown/no_explicit_tool_label" in text
