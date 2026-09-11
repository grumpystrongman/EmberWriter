from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .storage import project_root, safe_project_path, utc_now


def _require_project(slug: str) -> Path:
    root = project_root(slug)
    if not (root / "project.json").exists():
        raise FileNotFoundError(slug)
    return root


def _db_path(slug: str) -> Path:
    root = _require_project(slug)
    path = root / ".ember" / "story.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect(slug: str) -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(slug))
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS writing_sprints (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            start_words INTEGER NOT NULL,
            end_words INTEGER,
            target_words INTEGER NOT NULL,
            duration_minutes INTEGER NOT NULL,
            elapsed_seconds INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'active'
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_writing_sprints_started "
        "ON writing_sprints(started_at DESC)"
    )
    con.commit()
    return con


def _elapsed_seconds(started_at: str, ended_at: str | None = None) -> int:
    started = datetime.fromisoformat(started_at)
    ended = datetime.fromisoformat(ended_at) if ended_at else datetime.now(UTC)
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    if ended.tzinfo is None:
        ended = ended.replace(tzinfo=UTC)
    return max(0, int((ended - started).total_seconds()))


def _serialize(row: sqlite3.Row | dict) -> dict:
    item = dict(row)
    end_words = item.get("end_words")
    net_words = (end_words - item["start_words"]) if end_words is not None else None
    elapsed = item.get("elapsed_seconds") or _elapsed_seconds(item["started_at"], item.get("ended_at"))
    item["elapsed_seconds"] = elapsed
    item["net_words"] = net_words
    item["words_per_minute"] = (
        round(net_words / max(elapsed / 60, 1 / 60), 1)
        if net_words is not None and elapsed > 0
        else None
    )
    return item


def start_sprint(
    slug: str,
    path: str,
    start_words: int,
    target_words: int,
    duration_minutes: int,
) -> dict:
    source_path = safe_project_path(slug, path)
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(path)
    sprint_id = uuid4().hex
    started_at = utc_now()
    with _connect(slug) as con:
        active = con.execute(
            "SELECT id, started_at FROM writing_sprints WHERE status = 'active' ORDER BY started_at DESC"
        ).fetchall()
        for row in active:
            ended_at = utc_now()
            con.execute(
                "UPDATE writing_sprints SET status = 'cancelled', ended_at = ?, elapsed_seconds = ? WHERE id = ?",
                (ended_at, _elapsed_seconds(row["started_at"], ended_at), row["id"]),
            )
        con.execute(
            """
            INSERT INTO writing_sprints
            (id, path, started_at, start_words, target_words, duration_minutes, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            """,
            (sprint_id, path, started_at, start_words, target_words, duration_minutes),
        )
        row = con.execute("SELECT * FROM writing_sprints WHERE id = ?", (sprint_id,)).fetchone()
    return _serialize(row)


def finish_sprint(slug: str, sprint_id: str, end_words: int, status: str = "completed") -> dict:
    if status not in {"completed", "cancelled"}:
        raise ValueError("Sprint status must be completed or cancelled")
    ended_at = utc_now()
    with _connect(slug) as con:
        current = con.execute("SELECT * FROM writing_sprints WHERE id = ?", (sprint_id,)).fetchone()
        if current is None:
            raise FileNotFoundError(sprint_id)
        elapsed = _elapsed_seconds(current["started_at"], ended_at)
        con.execute(
            """
            UPDATE writing_sprints
            SET ended_at = ?, end_words = ?, elapsed_seconds = ?, status = ?
            WHERE id = ?
            """,
            (ended_at, end_words, elapsed, status, sprint_id),
        )
        row = con.execute("SELECT * FROM writing_sprints WHERE id = ?", (sprint_id,)).fetchone()
    return _serialize(row)


def active_sprint(slug: str) -> dict | None:
    with _connect(slug) as con:
        row = con.execute(
            "SELECT * FROM writing_sprints WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
    return _serialize(row) if row is not None else None


def list_sprints(slug: str, limit: int = 50) -> list[dict]:
    with _connect(slug) as con:
        rows = con.execute(
            "SELECT * FROM writing_sprints ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_serialize(row) for row in rows]
