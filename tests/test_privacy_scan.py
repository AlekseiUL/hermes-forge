import os
import subprocess
import sys
from pathlib import Path


def test_privacy_scan_passes_generated_artifacts(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    out = tmp_path / "out"
    env = {**os.environ, "PYTHONPATH": str(repo / "src")}
    subprocess.run([sys.executable, "-m", "hermes_forge.cli", "scan", "--hermes-home", str(fixture), "--all-profiles", "--out", str(out)], cwd=repo, env=env, check=True)
    proc = subprocess.run([sys.executable, "scripts/privacy_scan.py", str(out)], cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert proc.returncode == 0, proc.stdout
