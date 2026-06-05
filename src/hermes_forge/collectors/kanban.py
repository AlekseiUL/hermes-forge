from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path

from hermes_forge.models import EvidenceItem
from hermes_forge.redaction import safe_path_label

KNOWN_STATUS_LABELS = {
    "backlog", "todo", "pending", "in_progress", "review", "blocked", "done", "completed", "cancelled", "canceled", "unknown"
}


def _open_readonly(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    return sqlite3.connect(uri, uri=True)


def _safe_status(raw: object) -> str:
    label = str(raw or "unknown").strip().lower().replace(" ", "_").replace("-", "_")[:40]
    if not label:
        return "unknown"
    if label in KNOWN_STATUS_LABELS:
        return label
    return "custom:redacted"


def _has_symlink_component(path: Path) -> bool:
    absolute = path.expanduser().absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.is_symlink():
            return True
    return False


def collect_kanban_evidence(db_path: Path | None, hermes_home: Path, start_id: int = 1) -> list[EvidenceItem]:
    if db_path is None:
        return []
    candidate = db_path.expanduser()
    if candidate.is_symlink() or _has_symlink_component(candidate) or not candidate.is_file():
        return [EvidenceItem(
            id=f"ev-{start_id:06d}", source_type="kanban_db", source_ref=safe_path_label(candidate, hermes_home), profile="external",
            component="kanban", finding_type="kanban_adapter_unavailable", fact="Kanban DB path is not a regular file or is a symlink; adapter skipped.",
            interpretation="Forge does not follow Kanban DB symlinks or non-file paths.", severity="low", confidence="high", privacy="shareable-aggregate",
            suggested_targets=["collector_safety"],
        )]
    resolved = candidate.resolve()
    try:
        with _open_readonly(resolved) as conn:
            tables = {str(r[0]) for r in conn.execute("select name from sqlite_master where type='table'").fetchall()}
            table = "cards" if "cards" in tables else "tasks" if "tasks" in tables else None
            if table is None:
                return [EvidenceItem(
                    id=f"ev-{start_id:06d}", source_type="kanban_db", source_ref=safe_path_label(resolved, hermes_home), profile="external",
                    component="kanban", finding_type="kanban_schema_unknown", fact="Kanban DB found, but supported cards/tasks table is absent.",
                    interpretation="Unknown Kanban schemas are skipped rather than guessed.", severity="low", confidence="high", privacy="shareable-aggregate",
                    suggested_targets=["adapter_schema_review"],
                )]
            columns = [r[1] for r in conn.execute(f"pragma table_info({table})").fetchall()]
            if "status" not in columns:
                return [EvidenceItem(
                    id=f"ev-{start_id:06d}", source_type="kanban_db", source_ref=safe_path_label(resolved, hermes_home), profile="external",
                    component="kanban", finding_type="kanban_schema_unknown", fact="Kanban table lacks a status column; adapter skipped.",
                    interpretation="Kanban import requires status metadata and never reads card bodies by default.", severity="low", confidence="high", privacy="shareable-aggregate",
                    suggested_targets=["adapter_schema_review"],
                )]
            rows = conn.execute(f"select status from {table}").fetchall()
            counts = Counter(_safe_status(row[0]) for row in rows)
            assignee_count = 0
            if "assignee" in columns:
                assignee_count = int(conn.execute(f"select count(distinct assignee) from {table} where assignee is not null and assignee != ''").fetchone()[0])
            parts = ", ".join(f"{k}={counts[k]}" for k in sorted(counts)) or "none"
            return [EvidenceItem(
                id=f"ev-{start_id:06d}", source_type="kanban_db", source_ref=safe_path_label(resolved, hermes_home), profile="external",
                component="kanban", finding_type="kanban_workflow_signal", fact=f"Kanban metadata: cards={len(rows)}, status_counts={parts}, assignee_labels={assignee_count}.",
                interpretation="Aggregate task flow can reveal review/blocked/done patterns without copying card titles or bodies.", severity="low", confidence="medium", privacy="shareable-aggregate",
                suggested_targets=["workflow_eval_candidate", "proposal_evidence"],
            )]
    except sqlite3.Error:
        return [EvidenceItem(
            id=f"ev-{start_id:06d}", source_type="kanban_db", source_ref=safe_path_label(resolved, hermes_home), profile="external",
            component="kanban", finding_type="kanban_adapter_unavailable", fact="Kanban DB could not be opened read-only or has an unsupported/corrupt shape.",
            interpretation="Forge reports adapter unavailability instead of mutating or repairing DB files.", severity="low", confidence="high", privacy="shareable-aggregate",
            suggested_targets=["adapter_schema_review"],
        )]
