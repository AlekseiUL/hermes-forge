from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run(args, cwd: Path):
    env = {**os.environ, "PYTHONPATH": str(cwd / "src")}
    return subprocess.run([sys.executable, "-m", "hermes_forge.cli", *args], cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def test_doctor_self_check_has_no_apply_or_side_effects():
    repo = Path(__file__).resolve().parents[1]
    p = run(["doctor"], repo)
    assert p.returncode == 0, p.stdout
    data = json.loads(p.stdout)
    assert data["status"] == "OK"
    assert data["apply_enabled"] is False
    assert data["schema_version"] == "hermes-forge.doctor/v1"
    assert "APPLY_BLOCKED_NO_EXECUTOR" in p.stdout
    assert "APPLY_DISABLED_IN_MVP" in p.stdout


def test_capabilities_are_machine_readable_and_safe():
    repo = Path(__file__).resolve().parents[1]
    p = run(["capabilities"], repo)
    assert p.returncode == 0, p.stdout
    data = json.loads(p.stdout)
    assert data["schema_version"] == "hermes-forge.capabilities/v1"
    assert data["apply_supported"] is False
    assert data["apply_status"] == "APPLY_BLOCKED_NO_EXECUTOR"
    assert data["legacy_apply_status"] == "APPLY_DISABLED_IN_MVP"
    assert data["apply_executor_registered"] is False
    assert data["side_effects"]["edits_hermes_home"] is False
    assert data["side_effects"]["network_required"] is False
    assert data["adapters"]["kanban"]["status"] == "optional_path"


def test_doctor_does_not_require_live_hermes_home(tmp_path: Path, monkeypatch):
    repo = Path(__file__).resolve().parents[1]
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "missing-home"))
    p = run(["doctor"], repo)
    assert p.returncode == 0, p.stdout
    data = json.loads(p.stdout)
    assert data["status"] == "OK"
