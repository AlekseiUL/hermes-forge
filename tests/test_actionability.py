from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run(args, cwd: Path):
    env = {**os.environ, "PYTHONPATH": str(cwd / "src")}
    return subprocess.run([sys.executable, "-m", "hermes_forge.cli", *args], cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def test_findings_are_prioritized_and_proposals_have_next_checks(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    out = tmp_path / "forge"
    assert run(["scan", "--hermes-home", str(fixture), "--all-profiles", "--out", str(out)], repo).returncode == 0
    assert run(["analyze", "--scan", str(out), "--out", str(out / "analysis")], repo).returncode == 0
    findings = json.loads((out / "analysis" / "findings.json").read_text())
    assert findings["findings"]
    first = findings["findings"][0]
    assert first["priority_score"] > 0
    assert first["priority_label"] in {"low", "medium", "high", "critical"}
    assert first["next_checks"]
    assert first["review_focus"]
    assert run(["propose", "--analysis", str(out / "analysis"), "--out", str(out / "proposals")], repo).returncode == 0
    proposal = json.loads((out / "proposals" / "prop-0001" / "proposal.json").read_text())
    assert proposal["priority_score"] > 0
    assert proposal["next_checks"]
    md = (out / "proposals" / "prop-0001" / "proposal.md").read_text()
    assert "## Priority" in md
    assert "## Next checks" in md
    assert "review card" in md
