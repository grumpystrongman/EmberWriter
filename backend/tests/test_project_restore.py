import json
import sqlite3
from pathlib import Path

import pytest

from app import project_restore, storage


def _project_json(name: str = "Old Novel") -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "id": "old-id",
            "slug": "old-novel",
            "name": name,
            "description": "Original description",
            "content_profile": {"audience": "adult", "heat_level": "author_controlled"},
        }
    ).encode()


def test_restore_uploaded_project_preserves_tree_and_ember_history(
    tmp_path: Path, monkeypatch
) -> None:
    storage.DATA_ROOT = tmp_path / "data"
    storage.PROJECTS_ROOT = storage.DATA_ROOT / "projects"

    result = project_restore.restore_uploaded_project(
        [
            ("OldNovel/project.json", _project_json()),
            ("OldNovel/manuscript/chapter-003.md", b"# Chapter 3\n\nOriginal prose."),
            ("OldNovel/world/city.md", b"# City\n\nCanon."),
            ("OldNovel/.ember/story.db", b"not-a-sqlite-db-but-preserve-it"),
        ]
    )

    slug = result["project"]["slug"]
    root = storage.PROJECTS_ROOT / slug
    assert result["project"]["name"] == "Old Novel"
    assert (root / "manuscript" / "chapter-003.md").read_text(encoding="utf-8").endswith(
        "Original prose."
    )
    assert (root / "world" / "city.md").read_text(encoding="utf-8").endswith("Canon.")
    assert (root / ".ember" / "story.db").read_bytes() == b"not-a-sqlite-db-but-preserve-it"
    assert not (root / "manuscript" / "chapter-001.md").exists()
    target_meta = json.loads((root / "project.json").read_text(encoding="utf-8"))
    assert target_meta["id"] != "old-id"
    assert target_meta["source_project_id"] == "old-id"
    assert target_meta["restored_from_upload"] is True


def test_restore_uploaded_history_only_project_reconstructs_manuscript(
    tmp_path: Path, monkeypatch
) -> None:
    storage.DATA_ROOT = tmp_path / "data"
    storage.PROJECTS_ROOT = storage.DATA_ROOT / "projects"
    source_db = tmp_path / "story.db"
    content = "# Chapter 11\n\nRecovered from the uploaded revision database."
    with sqlite3.connect(source_db) as con:
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
                "rev-11",
                "manuscript/chapter-011.md",
                None,
                "2026-09-13T12:00:00+00:00",
                "save",
                "",
                "hash",
                len(content.split()),
                content,
            ),
        )

    result = project_restore.restore_uploaded_project(
        [
            ("LostBook/project.json", _project_json("Lost Book")),
            ("LostBook/.ember/story.db", source_db.read_bytes()),
        ]
    )

    slug = result["project"]["slug"]
    chapter = storage.PROJECTS_ROOT / slug / "manuscript" / "chapter-011.md"
    assert result["history_restored_count"] == 1
    assert chapter.read_text(encoding="utf-8").endswith("revision database.")


def test_restore_uploaded_project_rejects_non_emberwriter_folder(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path / "data"
    storage.PROJECTS_ROOT = storage.DATA_ROOT / "projects"

    with pytest.raises(ValueError, match="does not look like an EmberWriter project"):
        project_restore.restore_uploaded_project([("random-folder/photo.jpg", b"image")])


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../outside/project.json",
        "/absolute/project.json",
        r"C:\absolute\project.json",
    ],
)
def test_restore_uploaded_project_rejects_unsafe_paths(
    tmp_path: Path, unsafe_path: str
) -> None:
    storage.DATA_ROOT = tmp_path / "data"
    storage.PROJECTS_ROOT = storage.DATA_ROOT / "projects"

    with pytest.raises(ValueError, match="Unsafe project path"):
        project_restore.restore_uploaded_project([(unsafe_path, _project_json())])
