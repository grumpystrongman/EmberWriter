from __future__ import annotations

import difflib
import hashlib
import sqlite3
from pathlib import Path
from uuid import uuid4

from .storage import project_root, read_text, save_text, utc_now


def _db_path(slug: str) -> Path:
    path = project_root(slug) / ".ember" / "story.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect(slug: str) -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(slug))
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS document_revisions (
            id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            parent_revision_id TEXT,
            created_at TEXT NOT NULL,
            source TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL,
            word_count INTEGER NOT NULL DEFAULT 0,
            content TEXT NOT NULL
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_revisions_path_created "
        "ON document_revisions(path, created_at DESC)"
    )
    con.commit()
    return con


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _word_count(content: str) -> int:
    return len(content.split())


def _side_by_side_rows(older_content: str, newer_content: str) -> list[dict]:
    older_lines = older_content.splitlines()
    newer_lines = newer_content.splitlines()
    matcher = difflib.SequenceMatcher(a=older_lines, b=newer_lines, autojunk=False)
    rows: list[dict] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                rows.append(
                    {
                        "kind": "equal",
                        "older_line": i1 + offset + 1,
                        "newer_line": j1 + offset + 1,
                        "older_text": older_lines[i1 + offset],
                        "newer_text": newer_lines[j1 + offset],
                    }
                )
            continue

        if tag == "delete":
            for index in range(i1, i2):
                rows.append(
                    {
                        "kind": "delete",
                        "older_line": index + 1,
                        "newer_line": None,
                        "older_text": older_lines[index],
                        "newer_text": "",
                    }
                )
            continue

        if tag == "insert":
            for index in range(j1, j2):
                rows.append(
                    {
                        "kind": "insert",
                        "older_line": None,
                        "newer_line": index + 1,
                        "older_text": "",
                        "newer_text": newer_lines[index],
                    }
                )
            continue

        width = max(i2 - i1, j2 - j1)
        for offset in range(width):
            older_index = i1 + offset
            newer_index = j1 + offset
            has_older = older_index < i2
            has_newer = newer_index < j2
            rows.append(
                {
                    "kind": "change" if has_older and has_newer else ("delete" if has_older else "insert"),
                    "older_line": older_index + 1 if has_older else None,
                    "newer_line": newer_index + 1 if has_newer else None,
                    "older_text": older_lines[older_index] if has_older else "",
                    "newer_text": newer_lines[newer_index] if has_newer else "",
                }
            )

    return rows


def record_revision(
    slug: str,
    path: str,
    content: str | None = None,
    *,
    source: str = "save",
    note: str = "",
    force: bool = False,
) -> dict:
    content = read_text(slug, path) if content is None else content
    content_hash = _hash(content)
    with _connect(slug) as con:
        previous = con.execute(
            "SELECT id, content_hash FROM document_revisions WHERE path = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (path,),
        ).fetchone()
        if previous is not None and previous["content_hash"] == content_hash and not force:
            row = con.execute(
                "SELECT id, path, parent_revision_id, created_at, source, note, "
                "content_hash, word_count FROM document_revisions WHERE id = ?",
                (previous["id"],),
            ).fetchone()
            return {**dict(row), "created": False}

        revision_id = uuid4().hex
        con.execute(
            """
            INSERT INTO document_revisions
            (id, path, parent_revision_id, created_at, source, note, content_hash, word_count, content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                revision_id,
                path,
                previous["id"] if previous else None,
                utc_now(),
                source,
                note.strip(),
                content_hash,
                _word_count(content),
                content,
            ),
        )
        row = con.execute(
            "SELECT id, path, parent_revision_id, created_at, source, note, "
            "content_hash, word_count FROM document_revisions WHERE id = ?",
            (revision_id,),
        ).fetchone()
    return {**dict(row), "created": True}


def list_revisions(slug: str, path: str, limit: int = 200) -> list[dict]:
    with _connect(slug) as con:
        rows = con.execute(
            "SELECT id, path, parent_revision_id, created_at, source, note, "
            "content_hash, word_count FROM document_revisions WHERE path = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (path, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_revision(slug: str, revision_id: str) -> dict:
    with _connect(slug) as con:
        row = con.execute(
            "SELECT id, path, parent_revision_id, created_at, source, note, "
            "content_hash, word_count, content FROM document_revisions WHERE id = ?",
            (revision_id,),
        ).fetchone()
    if row is None:
        raise FileNotFoundError(revision_id)
    return dict(row)


def compare_revisions(slug: str, older_id: str, newer_id: str | None = None) -> dict:
    older = get_revision(slug, older_id)
    if newer_id:
        newer = get_revision(slug, newer_id)
    else:
        current = read_text(slug, older["path"])
        newer = {
            "id": "current",
            "path": older["path"],
            "created_at": utc_now(),
            "word_count": _word_count(current),
            "content": current,
        }
    if older["path"] != newer["path"]:
        raise ValueError("Revisions must belong to the same document")

    diff = "".join(
        difflib.unified_diff(
            older["content"].splitlines(keepends=True),
            newer["content"].splitlines(keepends=True),
            fromfile=f"revision:{older['id']}",
            tofile=f"revision:{newer['id']}",
            n=3,
        )
    )
    return {
        "path": older["path"],
        "older": {key: value for key, value in older.items() if key != "content"},
        "newer": {key: value for key, value in newer.items() if key != "content"},
        "diff": diff,
        "rows": _side_by_side_rows(older["content"], newer["content"]),
    }


def restore_revision(slug: str, revision_id: str, note: str = "") -> dict:
    revision = get_revision(slug, revision_id)
    save_text(slug, revision["path"], revision["content"])
    restored = record_revision(
        slug,
        revision["path"],
        revision["content"],
        source="restore",
        note=note or f"Restored revision {revision_id[:8]}",
        force=True,
    )
    return {"path": revision["path"], "restored_from": revision_id, "revision": restored}
