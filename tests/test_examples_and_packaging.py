from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run(args, cwd: Path):
    env = {**os.environ, "PYTHONPATH": str(cwd / "src")}
    return subprocess.run([sys.executable, "-m", "hermes_forge.cli", *args], cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def test_example_flow_outputs_privacy_scan_clean(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    out = tmp_path / "example"
    assert run(["scan", "--hermes-home", "tests/fixtures/hermes_home_minimal", "--all-profiles", "--kanban-db", "tests/fixtures/kanban/kanban.db", "--doctor-report", "tests/fixtures/doctor/report.json", "--out", str(out)], repo).returncode == 0
    assert run(["analyze", "--scan", str(out), "--out", str(out / "analysis")], repo).returncode == 0
    assert run(["propose", "--analysis", str(out / "analysis"), "--out", str(out / "proposals")], repo).returncode == 0
    assert run(["eval", "--proposal", str(out / "proposals" / "prop-0001" / "proposal.json"), "--out", str(out / "evals" / "prop-0001")], repo).returncode == 0
    scan = subprocess.run([sys.executable, "scripts/privacy_scan.py", str(out)], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    assert scan.returncode == 0, scan.stdout


def test_readme_mentions_apply_disabled_and_examples():
    repo = Path(__file__).resolve().parents[1]
    text = (repo / "README.md").read_text(encoding="utf-8")
    assert "APPLY_DISABLED_IN_MVP" in text
    assert "examples/" in text
    assert "not autonomous self-modification" in text.lower()
