from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run(args, cwd: Path):
    env = {**os.environ, "PYTHONPATH": str(cwd / "src")}
    return subprocess.run([sys.executable, "-m", "hermes_forge.cli", *args], cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def test_diff_preview_from_blocked_experiment_writes_preview_artifacts(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    improve_out = tmp_path / "improve"
    experiment_out = tmp_path / "experiment"
    diff_out = tmp_path / "diff"

    p1 = run(["improve", "--mode", "read-only", "--hermes-home", str(fixture), "--all-profiles", "--out", str(improve_out)], repo)
    assert p1.returncode == 0, p1.stdout
    p2 = run(["experiment", "--opportunity", str(improve_out / "opportunities.json"), "--id", "opp-0001", "--out", str(experiment_out)], repo)
    assert p2.returncode == 0, p2.stdout
    p3 = run(["diff-preview", "--experiment", str(experiment_out), "--hermes-home", str(fixture), "--out", str(diff_out)], repo)

    assert p3.returncode == 0, p3.stdout
    for name in ["diff-preview.json", "diff-preview.md", "proposed-files.json", "risk-check.json", "rollback-plan.md", "tests-to-run.md", "candidate-patch.json", "candidate.diff", "approval-checklist.md"]:
        assert (diff_out / name).exists(), name
    preview = json.loads((diff_out / "diff-preview.json").read_text())
    assert preview["status"] == "BLOCKED_NEEDS_OWNER_CONTEXT"
    assert preview["files_changed"] == 0
    assert preview["apply_enabled"] is False
    assert preview["proposed_files"] == []
    risk = json.loads((diff_out / "risk-check.json").read_text())
    assert risk["needs_owner_approval"] is True
    md = (diff_out / "diff-preview.md").read_text()
    assert "Forge did not edit" in md
    assert "did not write to Hermes home" in md


def test_diff_preview_preview_only_for_ready_experiment_result(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    experiment = tmp_path / "experiment"
    experiment.mkdir()
    (experiment / "experiment-plan.json").write_text(json.dumps({
        "schema_version": "hermes-forge.experiment-plan/v1",
        "opportunity_id": "opp-ready",
        "finding_id": "finding-ready",
        "opportunity_type": "skill_improvement",
        "proposal_type": "repair_plan",
        "opportunity_state": "ready_for_diff_preview",
        "safe_next_step_type": "open_diff",
        "hypothesis": "Skill frontmatter can be cleaned without rewriting private skill bodies.",
        "evidence_ids": ["evidence-1"],
    }), encoding="utf-8")
    (experiment / "experiment-result.json").write_text(json.dumps({
        "schema_version": "hermes-forge.experiment-result/v1",
        "opportunity_id": "opp-ready",
        "status": "READY_TO_RUN",
        "next_state": "ready_for_diff_preview",
        "files_changed": 0,
        "apply_enabled": False,
    }), encoding="utf-8")
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    out = tmp_path / "diff"

    p = run(["diff-preview", "--experiment", str(experiment), "--hermes-home", str(hermes_home), "--out", str(out)], repo)

    assert p.returncode == 0, p.stdout
    preview = json.loads((out / "diff-preview.json").read_text())
    assert preview["status"] == "PREVIEW_ONLY"
    assert preview["preview_type"] == "metadata_patch_preview"
    assert preview["files_changed"] == 0
    assert preview["apply_enabled"] is False
    proposed = json.loads((out / "proposed-files.json").read_text())["files"]
    assert proposed[0]["live_path"] is None
    assert proposed[0]["path_policy"] == "review-selected-skill-only"
    assert "No rollback is needed for this preview" in (out / "rollback-plan.md").read_text()
    candidate = json.loads((out / "candidate-patch.json").read_text())
    assert candidate["status"] == "CANDIDATE_PATCH_PREVIEW_ONLY"
    assert candidate["files_changed"] == 0
    assert candidate["apply_enabled"] is False
    assert candidate["live_path"] is None
    assert candidate["virtual_path"].startswith("hermes-forge-candidates/opp-ready/")
    patch = (out / "candidate.diff").read_text()
    assert "--- a/hermes-forge-candidates/opp-ready/skill_frontmatter.md" in patch
    assert "+++ b/hermes-forge-candidates/opp-ready/skill_frontmatter.md" in patch
    assert "+- live_path: null" in patch
    assert "Skill frontmatter can be cleaned" in patch
    checklist = (out / "approval-checklist.md").read_text()
    assert "apply command invoked separately" in checklist


def test_diff_preview_redacts_markdown_as_well_as_json(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    experiment = tmp_path / "experiment"
    experiment.mkdir()
    secret_value = "sk-" + "A" * 20
    secret_key = "tok" + "en"
    user_path = "/" + "Users" + "/private/project"
    (experiment / "experiment-plan.json").write_text(json.dumps({
        "schema_version": "hermes-forge.experiment-plan/v1",
        "opportunity_id": "opp-secret",
        "finding_id": "finding-secret",
        "opportunity_type": "skill_improvement",
        "proposal_type": "repair_plan",
        "opportunity_state": "ready_for_diff_preview",
        "safe_next_step_type": "open_diff",
        "hypothesis": f"Use {secret_key}={secret_value} at {user_path}",
        "evidence_ids": ["evidence-1"],
    }), encoding="utf-8")
    (experiment / "experiment-result.json").write_text(json.dumps({
        "schema_version": "hermes-forge.experiment-result/v1",
        "opportunity_id": "opp-secret",
        "status": "READY_TO_RUN",
        "next_state": "ready_for_diff_preview",
        "files_changed": 0,
        "apply_enabled": False,
    }), encoding="utf-8")
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    out = tmp_path / "diff"

    p = run(["diff-preview", "--experiment", str(experiment), "--hermes-home", str(hermes_home), "--out", str(out)], repo)

    assert p.returncode == 0, p.stdout
    combined = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in out.iterdir() if path.is_file())
    assert secret_value not in combined
    assert user_path not in combined
    assert "[REDACTED]" in combined
    candidate = json.loads((out / "candidate-patch.json").read_text())
    assert secret_value not in candidate.get("unified_diff", "")
    assert user_path not in candidate.get("unified_diff", "")


def test_diff_preview_blocks_out_under_hermes_home(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    hermes_home = tmp_path / "home"
    experiment = tmp_path / "experiment"
    hermes_home.mkdir()
    experiment.mkdir()
    (experiment / "experiment-plan.json").write_text('{"opportunity_id":"opp"}', encoding="utf-8")
    (experiment / "experiment-result.json").write_text('{"status":"READY_TO_RUN","next_state":"ready_for_diff_preview"}', encoding="utf-8")
    out = hermes_home / "bad-diff"

    p = run(["diff-preview", "--experiment", str(experiment), "--hermes-home", str(hermes_home), "--out", str(out)], repo)

    assert p.returncode == 2
    assert "OUT_UNDER_HERMES_HOME_BLOCKED" in p.stdout
    assert not out.exists()


def test_diff_preview_invalid_experiment_fails(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    hermes_home = tmp_path / "home"
    hermes_home.mkdir()
    out = tmp_path / "diff"

    p = run(["diff-preview", "--experiment", str(tmp_path / "missing"), "--hermes-home", str(hermes_home), "--out", str(out)], repo)

    assert p.returncode == 2
    assert "INVALID_EXPERIMENT" in p.stdout


def test_diff_preview_candidate_patch_not_created_for_blocked_state(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    hermes_home = tmp_path / "home"
    experiment = tmp_path / "experiment"
    hermes_home.mkdir()
    experiment.mkdir()
    (experiment / "experiment-plan.json").write_text(json.dumps({
        "opportunity_id": "opp-blocked",
        "opportunity_type": "config_review",
        "hypothesis": "Needs owner context first.",
    }), encoding="utf-8")
    (experiment / "experiment-result.json").write_text(json.dumps({
        "status": "BLOCKED_NEEDS_OWNER_CONTEXT",
        "next_state": "needs_owner_decision",
        "apply_enabled": False,
    }), encoding="utf-8")
    out = tmp_path / "diff"

    p = run(["diff-preview", "--experiment", str(experiment), "--hermes-home", str(hermes_home), "--out", str(out)], repo)

    assert p.returncode == 0, p.stdout
    candidate = json.loads((out / "candidate-patch.json").read_text())
    assert candidate["status"] == "NO_CANDIDATE_PATCH"
    assert candidate["candidate_files"] == []
    assert (out / "candidate.diff").read_text() == ""
