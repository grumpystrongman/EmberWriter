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
        "CREATE INDEX IF NOT EXISTS idx_writing_assistance_created "
        "ON writing_assistance_events(created_at DESC)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_writing_assistance_file "
        "ON writing_assistance_events(active_file, created_at DESC)"
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
