from __future__ import annotations

import sqlite3
from pathlib import Path

from hermes_forge.models import EvidenceItem
from hermes_forge.redaction import safe_path_label

SESSION_DB_CANDIDATES = (
    "sessions.db",
    "sessions.sqlite",
    "sessions.sqlite3",
    "sessions/sessions.db",
    "sessions/messages.db",
)


def _open_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    return sqlite3.connect(uri, uri=True)


def _has_symlink_between(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("select name from sqlite_master where type='table' order by name").fetchall()
    return {str(r[0]) for r in rows}


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"select count(*) from {table}").fetchone()[0])


def _minmax(conn: sqlite3.Connection, table: str, column: str) -> tuple[str | None, str | None]:
    row = conn.execute(f"select min({column}), max({column}) from {table}").fetchone()
    if not row:
        return None, None
    return (str(row[0]) if row[0] is not None else None, str(row[1]) if row[1] is not None else None)


def collect_session_evidence(profile_path: Path, profile_name: str, hermes_home: Path, start_id: int = 1) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    db_path = next((profile_path / rel for rel in SESSION_DB_CANDIDATES if (profile_path / rel).exists()), None)
    if db_path is None:
        return evidence
    if db_path.is_symlink() or _has_symlink_between(db_path, profile_path) or not db_path.is_file() or profile_path.resolve() not in db_path.resolve().parents:
        evidence.append(EvidenceItem(
            id=f"ev-{start_id:06d}",
            source_type="session_db",
            source_ref=safe_path_label(db_path, hermes_home),
            profile=profile_name,
            component="sessions",
            finding_type="session_adapter_unavailable",
            fact="Session DB path is not a regular file; adapter skipped.",
            interpretation="Forge does not follow session DB symlinks or non-file paths.",
            severity="low",
            confidence="high",
            privacy="shareable-aggregate",
            suggested_targets=["collector_safety"],
        ))
        return evidence
    try:
        with _open_readonly(db_path) as conn:
            tables = _tables(conn)
            if "sessions" not in tables:
                evidence.append(EvidenceItem(
                    id=f"ev-{start_id:06d}",
                    source_type="session_db",
                    source_ref=safe_path_label(db_path, hermes_home),
                    profile=profile_name,
                    component="sessions",
                    finding_type="session_schema_unknown",
                    fact="Session DB found, but supported sessions table is absent.",
                    interpretation="Unknown schemas are skipped rather than guessed.",
                    severity="low",
                    confidence="high",
                    privacy="shareable-aggregate",
                    suggested_targets=["adapter_schema_review"],
                ))
                return evidence
            sessions_count = _count(conn, "sessions")
            message_count = _count(conn, "messages") if "messages" in tables else 0
            cols = {row[1] for row in conn.execute("pragma table_info(sessions)").fetchall()}
            span = "unavailable"
            if "created_at" in cols:
                start, end = _minmax(conn, "sessions", "created_at")
                if start or end:
                    span = "present"
            evidence.append(EvidenceItem(
                id=f"ev-{start_id:06d}",
                source_type="session_db",
                source_ref=safe_path_label(db_path, hermes_home),
                profile=profile_name,
                component="sessions",
                finding_type="session_history_signal",
                fact=f"Session metadata: sessions={sessions_count}, messages={message_count}, time_span={span}.",
                interpretation="Aggregate session history can reveal repeated work/failure patterns without copying raw messages.",
                severity="low",
                confidence="medium",
                privacy="shareable-aggregate",
                suggested_targets=["session_eval_candidate", "proposal_evidence"],
            ))
            return evidence
    except sqlite3.Error:
        evidence.append(EvidenceItem(
            id=f"ev-{start_id:06d}",
            source_type="session_db",
            source_ref=safe_path_label(db_path, hermes_home),
            profile=profile_name,
            component="sessions",
            finding_type="session_adapter_unavailable",
            fact="Session DB could not be opened read-only or has an unsupported/corrupt shape.",
            interpretation="Forge reports adapter unavailability instead of mutating or repairing DB files.",
            severity="low",
            confidence="high",
            privacy="shareable-aggregate",
            suggested_targets=["adapter_schema_review"],
        ))
        return evidence
