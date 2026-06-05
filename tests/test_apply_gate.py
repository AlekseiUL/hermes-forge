from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run(args, cwd: Path):
    env = {**os.environ, "PYTHONPATH": str(cwd / "src")}
    return subprocess.run([sys.executable, "-m", "hermes_forge.cli", *args], cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def make_candidate(path: Path) -> dict:
    candidate = {
        "schema_version": "hermes-forge.candidate-patch/v1",
        "status": "CANDIDATE_PATCH_PREVIEW_ONLY",
        "reason": "review only",
        "files_changed": 0,
        "apply_enabled": False,
        "requires_approval_before_apply": True,
        "approval_id": "approve:hermes-forge-candidates/opp-ready/skill_frontmatter.md",
        "virtual_path": "hermes-forge-candidates/opp-ready/skill_frontmatter.md",
        "live_path": None,
        "candidate_files": [],
        "unified_diff": "--- a/hermes-forge-candidates/opp-ready/skill_frontmatter.md\n+++ b/hermes-forge-candidates/opp-ready/skill_frontmatter.md\n",
    }
    path.write_text(json.dumps(candidate), encoding="utf-8")
    return candidate


def test_apply_candidate_prechecks_pass_then_block_no_executor(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    target = home / "profiles" / "operator" / "skills" / "demo" / "SKILL.md"
    target.parent.mkdir(parents=True)
    target.write_text("name: demo\n", encoding="utf-8")
    candidate_path = tmp_path / "candidate-patch.json"
    candidate = make_candidate(candidate_path)
    out = tmp_path / "apply-out"

    p = run([
        "apply",
        "--candidate", str(candidate_path),
        "--approve", candidate["approval_id"],
        "--live-target", str(target),
        "--hermes-home", str(home),
        "--out", str(out),
    ], repo)

    assert p.returncode == 2
    result = json.loads(p.stdout)
    assert result["status"] == "APPLY_BLOCKED_NO_EXECUTOR"
    assert result["files_changed"] == 0
    assert result["apply_enabled"] is False
    assert result["executor_ran"] is False
    assert target.read_text(encoding="utf-8") == "name: demo\n"
    plan = json.loads((out / "apply-plan.json").read_text())
    assert plan["approval_matched"] is True
    assert plan["live_target"].startswith("<hermes-home>/")
    assert all(g["status"] == "pass" for g in plan["gates"] if g["name"] != "executor_registered")
    assert [g for g in plan["gates"] if g["name"] == "executor_registered"][0]["status"] == "fail"
    backup = json.loads((out / "backup-manifest.json").read_text())
    assert backup["status"] == "BACKUP_NOT_CREATED_NO_EXECUTOR"
    assert (out / "apply-plan.md").exists()


def test_apply_candidate_missing_approval_blocks_before_executor(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    target = home / "target.md"
    target.parent.mkdir(parents=True)
    target.write_text("x\n", encoding="utf-8")
    candidate_path = tmp_path / "candidate-patch.json"
    make_candidate(candidate_path)
    out = tmp_path / "apply-out"

    p = run([
        "apply",
        "--candidate", str(candidate_path),
        "--approve", "wrong-approval",
        "--live-target", str(target),
        "--hermes-home", str(home),
        "--out", str(out),
    ], repo)

    assert p.returncode == 2
    result = json.loads(p.stdout)
    assert result["status"] == "APPLY_BLOCKED_PRECHECK_FAILED"
    plan = json.loads((out / "apply-plan.json").read_text())
    approval_gate = [g for g in plan["gates"] if g["name"] == "approval"][0]
    assert approval_gate["status"] == "fail"
    assert target.read_text(encoding="utf-8") == "x\n"


def test_apply_candidate_blocks_out_under_hermes_home_before_writing(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    home.mkdir()
    target = home / "target.md"
    target.write_text("x\n", encoding="utf-8")
    candidate_path = tmp_path / "candidate-patch.json"
    candidate = make_candidate(candidate_path)
    out = home / "apply-out"

    p = run([
        "apply",
        "--candidate", str(candidate_path),
        "--approve", candidate["approval_id"],
        "--live-target", str(target),
        "--hermes-home", str(home),
        "--out", str(out),
    ], repo)

    assert p.returncode == 2
    assert "OUT_UNDER_HERMES_HOME_BLOCKED" in p.stdout
    assert not out.exists()
    assert target.read_text(encoding="utf-8") == "x\n"


def test_apply_candidate_requires_arguments(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    candidate_path = tmp_path / "candidate-patch.json"
    make_candidate(candidate_path)

    p = run(["apply", "--candidate", str(candidate_path)], repo)

    assert p.returncode == 2
    assert "APPLY_BLOCKED_MISSING_ARGUMENTS" in p.stdout


def test_legacy_apply_proposal_remains_disabled(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    proposal = tmp_path / "proposal.json"
    proposal.write_text("{}", encoding="utf-8")

    p = run(["apply", "--proposal", str(proposal)], repo)

    assert p.returncode == 2
    assert "APPLY_DISABLED_IN_MVP" in p.stdout


def test_apply_candidate_refuses_preexisting_hardlinked_artifact(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    target = home / "target.md"
    home.mkdir()
    target.write_text("LIVE\n", encoding="utf-8")
    candidate_path = tmp_path / "candidate-patch.json"
    candidate = make_candidate(candidate_path)
    out = tmp_path / "apply-out"
    out.mkdir()
    os.link(target, out / "apply-plan.json")

    p = run([
        "apply",
        "--candidate", str(candidate_path),
        "--approve", candidate["approval_id"],
        "--live-target", str(target),
        "--hermes-home", str(home),
        "--out", str(out),
    ], repo)

    assert p.returncode == 2
    result = json.loads(p.stdout)
    assert result["status"] == "APPLY_ARTIFACT_WRITE_BLOCKED"
    assert "hardlinked" in result["reason"]
    assert target.read_text(encoding="utf-8") == "LIVE\n"


def test_apply_candidate_refuses_preexisting_symlink_artifact_without_traceback(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    target = home / "target.md"
    home.mkdir()
    target.write_text("LIVE\n", encoding="utf-8")
    candidate_path = tmp_path / "candidate-patch.json"
    candidate = make_candidate(candidate_path)
    out = tmp_path / "apply-out"
    out.mkdir()
    (out / "apply-plan.json").symlink_to(target)

    p = run([
        "apply",
        "--candidate", str(candidate_path),
        "--approve", candidate["approval_id"],
        "--live-target", str(target),
        "--hermes-home", str(home),
        "--out", str(out),
    ], repo)

    assert p.returncode == 2
    assert "Traceback" not in p.stdout
    result = json.loads(p.stdout)
    assert result["status"] == "APPLY_ARTIFACT_WRITE_BLOCKED"
    assert target.read_text(encoding="utf-8") == "LIVE\n"


def test_apply_candidate_refuses_symlink_artifact_even_when_target_is_inside_out(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    target = home / "target.md"
    home.mkdir()
    target.write_text("LIVE\n", encoding="utf-8")
    candidate_path = tmp_path / "candidate-patch.json"
    candidate = make_candidate(candidate_path)
    out = tmp_path / "apply-out"
    out.mkdir()
    inner = out / "other.json"
    inner.write_text("INNER\n", encoding="utf-8")
    (out / "apply-plan.json").symlink_to(inner)

    p = run([
        "apply",
        "--candidate", str(candidate_path),
        "--approve", candidate["approval_id"],
        "--live-target", str(target),
        "--hermes-home", str(home),
        "--out", str(out),
    ], repo)

    assert p.returncode == 2
    result = json.loads(p.stdout)
    assert result["status"] == "APPLY_ARTIFACT_WRITE_BLOCKED"
    assert "symlink" in result["reason"]
    assert inner.read_text(encoding="utf-8") == "INNER\n"
    assert target.read_text(encoding="utf-8") == "LIVE\n"
