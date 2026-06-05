from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run(args, cwd: Path):
    env = {**os.environ, "PYTHONPATH": str(cwd / "src")}
    return subprocess.run([sys.executable, "-m", "hermes_forge.cli", *args], cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def test_experiment_blocks_owner_decision_opportunity_without_mutation(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    improve_out = tmp_path / "improve"
    experiment_out = tmp_path / "experiment"

    p1 = run(["improve", "--mode", "read-only", "--hermes-home", str(fixture), "--all-profiles", "--out", str(improve_out)], repo)
    assert p1.returncode == 0, p1.stdout
    p2 = run(["experiment", "--opportunity", str(improve_out / "opportunities.json"), "--id", "opp-0001", "--out", str(experiment_out)], repo)

    assert p2.returncode == 0, p2.stdout
    for name in ["experiment-plan.json", "experiment-result.json", "checks.json", "expected-outcome.md", "experiment.md"]:
        assert (experiment_out / name).exists(), name
    result = json.loads((experiment_out / "experiment-result.json").read_text())
    assert result["status"] == "BLOCKED_NEEDS_OWNER_CONTEXT"
    assert result["files_changed"] == 0
    assert result["apply_enabled"] is False
    plan = json.loads((experiment_out / "experiment-plan.json").read_text())
    assert plan["forbidden_side_effects"]
    assert "edit_hermes_home" in plan["forbidden_side_effects"]
    report = (experiment_out / "experiment.md").read_text()
    assert "This is a safe experiment plan/result" in report
    assert "did not edit Hermes home" in report


def test_experiment_ready_and_run_for_allowlisted_create_eval(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    source = tmp_path / "opportunities.json"
    source.write_text(json.dumps({
        "schema_version": "hermes-forge.opportunities/v1",
        "opportunities": [{
            "id": "opp-9999",
            "finding_id": "finding-9999",
            "opportunity_type": "reliability_risk",
            "proposal_type": "experiment",
            "opportunity_state": "ready_for_experiment",
            "safe_next_step_type": "create_eval",
            "improvement_hypothesis": "Synthetic classifier experiment can prove grouping without raw command arguments.",
            "evidence_ids": ["evidence-1"],
            "eval_plan": {
                "schema_version": "hermes-forge.eval-plan/v2",
                "command": "pytest -q tests/test_log_classifiers.py",
                "fixture": "synthetic runtime log fixture",
                "success_signal": "classifier groups categories without raw args",
                "writes_live_hermes_home": False,
                "requires_approval_before_apply": True,
            },
        }],
    }), encoding="utf-8")
    ready_out = tmp_path / "ready"
    run_out = tmp_path / "run"

    p1 = run(["experiment", "--opportunity", str(source), "--id", "opp-9999", "--out", str(ready_out)], repo)
    assert p1.returncode == 0, p1.stdout
    ready = json.loads((ready_out / "experiment-result.json").read_text())
    assert ready["status"] == "READY_TO_RUN"
    assert ready["runner_available"] is True

    p2 = run(["experiment", "--opportunity", str(source), "--id", "opp-9999", "--out", str(run_out), "--run"], repo)
    assert p2.returncode == 0, p2.stdout
    result = json.loads((run_out / "experiment-result.json").read_text())
    assert result["status"] == "READY_TO_RUN"
    assert result["next_state"] == "ready_for_experiment"
    assert "did not execute" in result["interpretation"]
    plan = json.loads((run_out / "experiment-plan.json").read_text())
    assert plan["eval_plan"]["writes_live_hermes_home"] is False


def test_experiment_rejects_allowlist_prefix_with_extra_suffix(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    source = tmp_path / "opportunities.json"
    source.write_text(json.dumps({
        "opportunities": [{
            "id": "opp-suffix",
            "finding_id": "finding-suffix",
            "opportunity_type": "reliability_risk",
            "proposal_type": "experiment",
            "opportunity_state": "ready_for_experiment",
            "safe_next_step_type": "create_eval",
            "improvement_hypothesis": "Suffix injection must not be treated as allowlisted.",
            "evidence_ids": ["evidence-1"],
            "eval_plan": {
                "schema_version": "hermes-forge.eval-plan/v2",
                "command": "pytest -q tests/test_log_classifiers.py --not-allowlisted",
                "fixture": "synthetic runtime log fixture",
                "success_signal": "should stay plan only",
                "writes_live_hermes_home": False,
                "requires_approval_before_apply": True,
            },
        }]
    }), encoding="utf-8")
    out = tmp_path / "experiment"

    p = run(["experiment", "--opportunity", str(source), "--id", "opp-suffix", "--out", str(out), "--run"], repo)

    assert p.returncode == 0, p.stdout
    result = json.loads((out / "experiment-result.json").read_text())
    assert result["status"] == "PLAN_ONLY"
    assert result["runner_available"] is False


def test_experiment_missing_id_fails_without_writing_artifacts(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    source = tmp_path / "opportunities.json"
    source.write_text('{"opportunities": []}', encoding="utf-8")
    out = tmp_path / "experiment"

    p = run(["experiment", "--opportunity", str(source), "--id", "opp-missing", "--out", str(out)], repo)

    assert p.returncode == 2
    assert "OPPORTUNITY_NOT_FOUND" in p.stdout
