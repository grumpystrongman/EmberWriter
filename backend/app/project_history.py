from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from uuid import uuid4

from .storage import _iter_story_files, project_root, read_text, save_text, utc_now


def _db_path(slug: str) -> Path:
    path = project_root(slug) / ".ember" / "story.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect(slug: str) -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(slug))
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS project_checkpoints (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            label TEXT NOT NULL,
            note TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'manual',
            file_count INTEGER NOT NULL DEFAULT 0,
            total_bytes INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS project_checkpoint_files (
            checkpoint_id TEXT NOT NULL,
            path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            content TEXT NOT NULL,
            PRIMARY KEY (checkpoint_id, path),
            FOREIGN KEY (checkpoint_id) REFERENCES project_checkpoints(id) ON DELETE CASCADE
        )
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_checkpoints_created "
        "ON project_checkpoints(created_at DESC)"
    )
    con.commit()
    return con


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _capture_files(slug: str) -> list[tuple[str, str, str]]:
    root = project_root(slug)
    files: list[tuple[str, str, str]] = []
    for absolute in _iter_story_files(slug):
        relative = str(absolute.relative_to(root)).replace("\\", "/")
        if relative.startswith("exports/"):
            continue
        try:
            content = absolute.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        files.append((relative, _hash(content), content))
    return sorted(files, key=lambda item: item[0])


def create_project_checkpoint(
    slug: str,
    label: str,
    note: str = "",
    *,
    source: str = "manual",
) -> dict:
    if not project_root(slug).exists():
        raise FileNotFoundError(slug)
    clean_label = label.strip() or "Project checkpoint"
    files = _capture_files(slug)
    checkpoint_id = uuid4().hex
    created_at = utc_now()
    total_bytes = sum(len(content.encode("utf-8")) for _, _, content in files)
    with _connect(slug) as con:
        con.execute(
            """
            INSERT INTO project_checkpoints
            (id, created_at, label, note, source, file_count, total_bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                checkpoint_id,
                created_at,
                clean_label,
                note.strip(),
                source,
                len(files),
                total_bytes,
            ),
        )
        con.executemany(
            """
            INSERT INTO project_checkpoint_files
            (checkpoint_id, path, content_hash, content)
            VALUES (?, ?, ?, ?)
            """,
            [(checkpoint_id, path, digest, content) for path, digest, content in files],
        )
    return {
        "id": checkpoint_id,
        "created_at": created_at,
        "label": clean_label,
        "note": note.strip(),
        "source": source,
        "file_count": len(files),
        "total_bytes": total_bytes,
    }


def list_project_checkpoints(slug: str, limit: int = 100) -> list[dict]:
    with _connect(slug) as con:
        rows = con.execute(
            """
            SELECT id, created_at, label, note, source, file_count, total_bytes
            FROM project_checkpoints
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_project_checkpoint(slug: str, checkpoint_id: str, include_content: bool = False) -> dict:
    with _connect(slug) as con:
        row = con.execute(
            """
            SELECT id, created_at, label, note, source, file_count, total_bytes
            FROM project_checkpoints WHERE id = ?
            """,
            (checkpoint_id,),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(checkpoint_id)
        file_rows = con.execute(
            """
            SELECT path, content_hash, content
            FROM project_checkpoint_files
            WHERE checkpoint_id = ? ORDER BY path
            """,
            (checkpoint_id,),
        ).fetchall()
    files = []
    for item in file_rows:
        payload = {"path": item["path"], "content_hash": item["content_hash"]}
        if include_content:
            payload["content"] = item["content"]
        files.append(payload)
    return {**dict(row), "files": files}


def compare_project_checkpoint(slug: str, checkpoint_id: str) -> dict:
    checkpoint = get_project_checkpoint(slug, checkpoint_id, include_content=False)
    previous = {item["path"]: item["content_hash"] for item in checkpoint["files"]}
    current = {path: digest for path, digest, _ in _capture_files(slug)}
    all_paths = sorted(set(previous) | set(current))
    changes = []
    for path in all_paths:
        if path not in previous:
            status = "added"
        elif path not in current:
            status = "deleted"
        elif previous[path] != current[path]:
            status = "modified"
        else:
            continue
        changes.append({"path": path, "status": status})
    return {
        "checkpoint": {key: value for key, value in checkpoint.items() if key != "files"},
        "changes": changes,
        "changed_files": len(changes),
    }


def restore_project_checkpoint(slug: str, checkpoint_id: str) -> dict:
    checkpoint = get_project_checkpoint(slug, checkpoint_id, include_content=True)
    safety = create_project_checkpoint(
        slug,
        f"Before restore: {checkpoint['label']}",
        f"Automatic safety checkpoint before restoring {checkpoint_id[:8]}",
        source="pre_restore",
    )
    root = project_root(slug)
    target_paths = {item["path"] for item in checkpoint["files"]}
    current_paths = {
        str(path.relative_to(root)).replace("\\", "/")
        for path in _iter_story_files(slug)
        if not str(path.relative_to(root)).replace("\\", "/").startswith("exports/")
    }

    removed: list[str] = []
    for relative in sorted(current_paths - target_paths):
        path = root / relative
        if path.is_file():
            path.unlink()
            removed.append(relative)

    restored: list[str] = []
    for item in checkpoint["files"]:
        save_text(slug, item["path"], item["content"])
        restored.append(item["path"])

    return {
        "restored_checkpoint_id": checkpoint_id,
        "safety_checkpoint_id": safety["id"],
        "restored_files": restored,
        "removed_files": removed,
    }
