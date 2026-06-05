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


def read_artifacts(out: Path) -> str:
    chunks = []
    for path in sorted(out.rglob("*")):
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


def test_phase1_sessions_kanban_doctor_metadata_only(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    kanban = repo / "tests" / "fixtures" / "kanban" / "kanban.db"
    doctor = repo / "tests" / "fixtures" / "doctor" / "report.json"
    before = snapshot_tree(fixture)
    out = tmp_path / "forge"
    p = run(["scan", "--hermes-home", str(fixture), "--all-profiles", "--kanban-db", str(kanban), "--doctor-report", str(doctor), "--out", str(out)], repo)
    assert p.returncode == 0, p.stdout
    assert snapshot_tree(fixture) == before
    assert not list(fixture.rglob("*.wal"))
    assert not list(fixture.rglob("*.shm"))
    summary = json.loads((out / "scan-summary.json").read_text())
    assert summary["adapters"]["sessions"]["mode"] == "metadata_only"
    assert summary["adapters"]["kanban"]["status"] == "enabled"
    assert summary["adapters"]["doctor_report"]["status"] == "enabled"
    text = read_artifacts(out)
    assert "Session metadata:" in text
    assert "Kanban metadata:" in text
    assert "Imported doctor report summary:" in text
    assert "Private customer title" not in text
    assert "Please debug" not in text
    assert "alice@example" not in text
    private_path = "/" + "Users" + "/private"
    assert private_path not in text


def test_unknown_kanban_schema_is_nonfatal(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    kanban = repo / "tests" / "fixtures" / "kanban" / "unknown.db"
    out = tmp_path / "forge"
    p = run(["scan", "--hermes-home", str(fixture), "--all-profiles", "--kanban-db", str(kanban), "--out", str(out)], repo)
    assert p.returncode == 0, p.stdout
    text = read_artifacts(out)
    assert "kanban_schema_unknown" in text


def test_no_change_proposal_is_first_class(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_empty"
    out = tmp_path / "forge"
    assert run(["scan", "--hermes-home", str(fixture), "--all-profiles", "--out", str(out)], repo).returncode == 0
    assert run(["analyze", "--scan", str(out), "--out", str(out / "analysis")], repo).returncode == 0
    assert run(["propose", "--analysis", str(out / "analysis"), "--out", str(out / "proposals")], repo).returncode == 0
    proposal_dir = out / "proposals" / "prop-0001"
    data = json.loads((proposal_dir / "proposal.json").read_text())
    assert data["target_type"] == "no_change"
    assert data["auto_apply_forbidden"] is True
    for name in ["proposal.md", "diff.preview", "eval-plan.md", "rollback.md"]:
        assert (proposal_dir / name).exists()
    p = run(["eval", "--proposal", str(proposal_dir / "proposal.json"), "--out", str(out / "evals" / "prop-0001")], repo)
    assert p.returncode == 0, p.stdout
    plan = json.loads((out / "evals" / "prop-0001" / "eval-plan.json").read_text())
    assert "evidence-insufficient" in plan["checks"]
    p = run(["apply", "--proposal", str(proposal_dir / "proposal.json")], repo)
    assert p.returncode == 2
    assert "APPLY_DISABLED_IN_MVP" in p.stdout


def test_eval_output_is_deterministic(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps({"id": "prop-stable", "target_type": "no_change"}), encoding="utf-8")
    out1 = tmp_path / "eval1"
    out2 = tmp_path / "eval2"
    assert run(["eval", "--proposal", str(proposal), "--out", str(out1)], repo).returncode == 0
    assert run(["eval", "--proposal", str(proposal), "--out", str(out2)], repo).returncode == 0
    assert (out1 / "eval-plan.json").read_text() == (out2 / "eval-plan.json").read_text()
    assert (out1 / "deterministic-checks.json").read_text() == (out2 / "deterministic-checks.json").read_text()



def test_optional_kanban_and_doctor_symlinks_are_skipped(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    kanban_target = repo / "tests" / "fixtures" / "kanban" / "kanban.db"
    doctor_target = repo / "tests" / "fixtures" / "doctor" / "report.json"
    kanban_link = tmp_path / "kanban-link.db"
    doctor_link = tmp_path / "doctor-link.json"
    kanban_link.symlink_to(kanban_target)
    doctor_link.symlink_to(doctor_target)
    out = tmp_path / "forge"
    p = run(["scan", "--hermes-home", str(fixture), "--all-profiles", "--kanban-db", str(kanban_link), "--doctor-report", str(doctor_link), "--out", str(out)], repo)
    assert p.returncode == 0, p.stdout
    text = read_artifacts(out)
    assert "kanban_adapter_unavailable" in text
    assert "doctor_report_unavailable" in text
    assert "Kanban metadata:" not in text
    assert "Imported doctor report summary:" not in text


def test_session_adapter_skips_symlinked_intermediate_directory(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    home = tmp_path / "home"
    home.mkdir()
    outside = tmp_path / "outside-sessions"
    outside.mkdir()
    db = outside / "sessions.db"
    import sqlite3
    conn = sqlite3.connect(db)
    conn.execute("create table sessions (id text, created_at text)")
    conn.execute("insert into sessions values ('s1','2026-01-01')")
    conn.commit(); conn.close()
    (home / "sessions").symlink_to(outside, target_is_directory=True)
    out = tmp_path / "forge"
    p = run(["scan", "--hermes-home", str(home), "--all-profiles", "--out", str(out)], repo)
    assert p.returncode == 0, p.stdout
    text = read_artifacts(out)
    assert "session_adapter_unavailable" in text
    assert "sessions=1" not in text


def test_kanban_status_labels_are_bucketed(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    db = tmp_path / "kanban.db"
    import sqlite3
    conn = sqlite3.connect(db)
    conn.execute("create table cards (id text, status text, assignee text)")
    conn.execute("insert into cards values ('1', 'Secret Project Codename With Spaces', 'person@example.invalid')")
    conn.commit(); conn.close()
    out = tmp_path / "forge"
    p = run(["scan", "--hermes-home", str(fixture), "--all-profiles", "--kanban-db", str(db), "--out", str(out)], repo)
    assert p.returncode == 0, p.stdout
    text = read_artifacts(out)
    assert "Secret Project" not in text
    assert "custom:redacted=1" in text



def test_optional_kanban_and_doctor_symlinked_parent_dirs_are_skipped(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    real = tmp_path / "real"
    real.mkdir()
    import shutil
    shutil.copy(repo / "tests" / "fixtures" / "kanban" / "kanban.db", real / "kanban.db")
    shutil.copy(repo / "tests" / "fixtures" / "doctor" / "report.json", real / "report.json")
    linkdir = tmp_path / "linkdir"
    linkdir.symlink_to(real, target_is_directory=True)
    out = tmp_path / "forge"
    p = run(["scan", "--hermes-home", str(fixture), "--all-profiles", "--kanban-db", str(linkdir / "kanban.db"), "--doctor-report", str(linkdir / "report.json"), "--out", str(out)], repo)
    assert p.returncode == 0, p.stdout
    text = read_artifacts(out)
    assert "kanban_adapter_unavailable" in text
    assert "doctor_report_unavailable" in text
    assert "Kanban metadata:" not in text
    assert "Imported doctor report summary:" not in text


def test_kanban_simple_unknown_status_does_not_leak_codename(tmp_path: Path):
    repo = Path(__file__).resolve().parents[1]
    fixture = repo / "tests" / "fixtures" / "hermes_home_minimal"
    db = tmp_path / "kanban.db"
    import sqlite3
    conn = sqlite3.connect(db)
    conn.execute("create table cards (id text, status text)")
    conn.execute("insert into cards values ('1', 'projectphoenix')")
    conn.commit(); conn.close()
    out = tmp_path / "forge"
    p = run(["scan", "--hermes-home", str(fixture), "--all-profiles", "--kanban-db", str(db), "--out", str(out)], repo)
    assert p.returncode == 0, p.stdout
    text = read_artifacts(out)
    assert "projectphoenix" not in text
    assert "custom:redacted=1" in text
