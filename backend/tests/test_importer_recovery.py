import json
import sqlite3
from pathlib import Path

from app import importer, storage


def test_local_project_import_preserves_ember_history(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path / "active-data"
    storage.PROJECTS_ROOT = storage.DATA_ROOT / "projects"

    source = tmp_path / "old-project"
    (source / "manuscript").mkdir(parents=True)
    (source / ".ember").mkdir()
    (source / "project.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "legacy-id",
                "slug": "legacy-book",
                "name": "Legacy Book",
                "description": "Recovered through local import",
            }
        ),
        encoding="utf-8",
    )
    (source / "manuscript" / "chapter.md").write_text(
        "# Chapter\n\nAuthor prose.", encoding="utf-8"
    )
    with sqlite3.connect(source / ".ember" / "story.db") as con:
        con.execute(
            """
            CREATE TABLE document_revisions (
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
            "INSERT INTO document_revisions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "rev-1",
                "manuscript/chapter.md",
                None,
                "2026-09-12T00:00:00+00:00",
                "save",
                "",
                "hash",
                3,
                "# Chapter\n\nOlder author prose.",
            ),
        )

    restored = importer.import_project(str(source))
    root = storage.PROJECTS_ROOT / restored["slug"]

    assert (root / "manuscript" / "chapter.md").read_text(encoding="utf-8").endswith("Author prose.")
    with sqlite3.connect(root / ".ember" / "story.db") as con:
        count = con.execute("SELECT COUNT(*) FROM document_revisions").fetchone()[0]
    assert count == 1
    assert source.exists()
