from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run(args, cwd: Path):
    env = {**os.environ, "PYTHONPATH": str(cwd / "src")}
    return subprocess.run([sys.executable, "-m", "hermes_forge.cli", *args], cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def test_fixture_flow_and_apply_disabled(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    out = tmp_path / "forge"
    p = run(["scan", "--hermes-home", str(fixture), "--all-profiles", "--out", str(out)], repo)
    assert p.returncode == 0, p.stdout
    assert (out / "evidence-ledger.jsonl").exists()
    p = run(["analyze", "--scan", str(out), "--out", str(out / "analysis")], repo)
    assert p.returncode == 0, p.stdout
    findings = json.loads((out / "analysis" / "findings.json").read_text())
    assert findings["findings"]
    p = run(["propose", "--analysis", str(out / "analysis"), "--out", str(out / "proposals")], repo)
    assert p.returncode == 0, p.stdout
    proposal = out / "proposals" / "prop-0001" / "proposal.json"
    assert proposal.exists()
    p = run(["eval", "--proposal", str(proposal), "--out", str(out / "evals" / "prop-0001")], repo)
    assert p.returncode == 0, p.stdout
    p = run(["apply", "--proposal", str(proposal)], repo)
    assert p.returncode == 2
    assert "APPLY_DISABLED_IN_MVP" in p.stdout


def test_scan_does_not_modify_fixture(tmp_path: Path):
    from hermes_forge.io_guard import snapshot_tree
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    before = snapshot_tree(fixture)
    p = run(["scan", "--hermes-home", str(fixture), "--all-profiles", "--out", str(tmp_path / "out")], repo)
    assert p.returncode == 0, p.stdout
    assert snapshot_tree(fixture) == before


def test_all_profiles_includes_default_and_named_profile(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    out = tmp_path / "out"
    p = run(["scan", "--hermes-home", str(fixture), "--all-profiles", "--out", str(out)], repo)
    assert p.returncode == 0, p.stdout
    inventory = json.loads((out / "inventory.json").read_text())
    names = {p["name"] for p in inventory["profiles"]}
    assert "default" in names
    assert "operator" in names


def test_scan_blocks_output_under_hermes_home(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    p = run(["scan", "--hermes-home", str(fixture), "--all-profiles", "--out", str(fixture / "forge-run")], repo)
    assert p.returncode == 2
    assert "OUT_UNDER_HERMES_HOME_BLOCKED" in p.stdout
