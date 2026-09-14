from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from .storage import project_root, utc_now

WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'’-]*\b")
ASSISTANCE_DECISIONS = {"accepted_append", "accepted_replace", "rejected", "partial", "copied"}


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _db_path(slug: str) -> Path:
    path = project_root(slug) / ".ember" / "story.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect(slug: str) -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(slug))
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS writing_assistance_events (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            mode TEXT NOT NULL,
            active_file TEXT,
            prompt_hash TEXT NOT NULL,
            selected_text_hash TEXT,
            output_hash TEXT NOT NULL,
            output_words INTEGER NOT NULL,
            context_files_json TEXT NOT NULL,
            refined INTEGER NOT NULL DEFAULT 0,
            provider TEXT NOT NULL,
            model TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS writing_assistance_decisions (
            assistance_event_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            decision TEXT NOT NULL,
            active_file TEXT,
            note TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(assistance_event_id) REFERENCES writing_assistance_events(id)
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_writing_assistance_created "
        "ON writing_assistance_events(created_at DESC)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_writing_assistance_file "
        "ON writing_assistance_events(active_file, created_at DESC)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_writing_assistance_decision_created "
        "ON writing_assistance_decisions(created_at DESC)"
    )
    con.commit()
    return con


def record_assistance_event(
    slug: str,
    *,
    mode: str,
    active_file: str | None,
    prompt: str,
    selected_text: str | None,
    output_text: str,
    context_files: list[str],
    refined: bool,
    provider: str,
    model: str,
) -> dict[str, Any]:
    event = {
        "id": uuid4().hex,
        "created_at": utc_now(),
        "mode": mode,
        "active_file": active_file or None,
        "prompt_hash": text_hash(prompt),
        "selected_text_hash": text_hash(selected_text) if selected_text else None,
        "output_hash": text_hash(output_text),
        "output_words": len(WORD_RE.findall(output_text)),
        "context_files": list(dict.fromkeys(context_files)),
        "refined": bool(refined),
        "provider": provider,
        "model": model,
    }
    with connect(slug) as con:
        con.execute(
            """
            INSERT INTO writing_assistance_events
            (id, created_at, mode, active_file, prompt_hash, selected_text_hash,
             output_hash, output_words, context_files_json, refined, provider, model)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["id"], event["created_at"], event["mode"], event["active_file"],
                event["prompt_hash"], event["selected_text_hash"], event["output_hash"],
                event["output_words"], json.dumps(event["context_files"], ensure_ascii=False),
                int(event["refined"]), event["provider"], event["model"],
            ),
        )
    return event


def record_assistance_decision(
    slug: str,
    *,
    assistance_event_id: str,
    decision: str,
    active_file: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    if decision not in ASSISTANCE_DECISIONS:
        raise ValueError(f"Unsupported assistance decision: {decision}")
    with connect(slug) as con:
        event = con.execute(
            "SELECT id FROM writing_assistance_events WHERE id = ?",
            (assistance_event_id,),
        ).fetchone()
        if event is None:
            raise FileNotFoundError(assistance_event_id)
        item = {
            "assistance_event_id": assistance_event_id,
            "created_at": utc_now(),
            "decision": decision,
            "active_file": active_file or None,
            "note": note.strip()[:1000],
        }
        con.execute(
            """
            INSERT INTO writing_assistance_decisions
            (assistance_event_id, created_at, decision, active_file, note)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(assistance_event_id) DO UPDATE SET
                created_at = excluded.created_at,
                decision = excluded.decision,
                active_file = excluded.active_file,
                note = excluded.note
            """,
            (
                item["assistance_event_id"], item["created_at"], item["decision"],
                item["active_file"], item["note"],
            ),
        )
    return item


def assistance_events(slug: str) -> list[dict[str, Any]]:
    with connect(slug) as con:
        rows = con.execute(
            "SELECT id, created_at, mode, active_file, prompt_hash, selected_text_hash, output_hash, "
            "output_words, context_files_json, refined, provider, model "
            "FROM writing_assistance_events ORDER BY created_at ASC"
        ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["context_files"] = json.loads(item.pop("context_files_json") or "[]")
        item["refined"] = bool(item["refined"])
        result.append(item)
    return result


def assistance_decisions(slug: str) -> list[dict[str, Any]]:
    with connect(slug) as con:
        rows = con.execute(
            "SELECT assistance_event_id, created_at, decision, active_file, note "
            "FROM writing_assistance_decisions ORDER BY created_at ASC"
        ).fetchall()
    return [dict(row) for row in rows]


def revision_rows(slug: str) -> list[dict[str, Any]]:
    with connect(slug) as con:
        exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'document_revisions'"
        ).fetchone()
        if not exists:
            return []
        rows = con.execute(
            "SELECT id, path, parent_revision_id, created_at, source, note, content_hash, word_count "
            "FROM document_revisions ORDER BY created_at ASC"
        ).fetchall()
    return [dict(row) for row in rows]
