import json
import sqlite3
from pathlib import Path

from app import project_recovery, storage


def _write_project(root: Path, *, slug: str, project_id: str, chapter: str) -> Path:
    project = root / "data" / "projects" / slug
    (project / "manuscript").mkdir(parents=True)
    (project / ".ember").mkdir(parents=True)
    (project / "project.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": project_id,
                "slug": slug,
                "name": "Recovered Novel",
                "description": "legacy work",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-09-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (project / "manuscript" / "chapter-001.md").write_text(chapter, encoding="utf-8")
    (project / ".ember" / "story.db").write_bytes(b"legacy-story-history")
    return project


def _write_metadata_less_project(root: Path, *, slug: str, chapter: str) -> Path:
    project = root / "archive" / slug
    (project / "manuscript").mkdir(parents=True)
    (project / "characters").mkdir()
    (project / "world").mkdir()
    (project / ".ember").mkdir()
    (project / "manuscript" / "chapter-009.md").write_text(chapter, encoding="utf-8")
    (project / ".ember" / "story.db").write_bytes(b"older-history")
    return project


def _write_history_only_project(root: Path, *, slug: str, content: str) -> Path:
    project = root / "data" / "projects" / slug
    ember = project / ".ember"
    ember.mkdir(parents=True)
    db_path = ember / "story.db"
    with sqlite3.connect(db_path) as con:
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
                "manuscript/chapter-004.md",
                None,
                "2026-09-12T10:00:00+00:00",
                "save",
                "",
                "hash",
                len(content.split()),
                content,
            ),
        )
    return project


def test_recovery_discovers_and_copies_legacy_project(tmp_path: Path, monkeypatch) -> None:
    active = tmp_path / "new-install" / "data"
    legacy_root = tmp_path / "old-install"
    source = _write_project(
        legacy_root,
        slug="old-novel",
        project_id="project-123",
        chapter="# Chapter 1\n\nThis is the previous manuscript.",
    )

    storage.DATA_ROOT = active
    storage.PROJECTS_ROOT = active / "projects"
    monkeypatch.setattr(project_recovery, "_search_roots", lambda: [legacy_root])
    monkeypatch.setattr(project_recovery, "_historical_windows_launch_roots", list)

    result = project_recovery.recover_legacy_projects()

    assert result["recovered_count"] == 1
    recovered = storage.PROJECTS_ROOT / "old-novel"
    assert recovered.exists()
    assert (recovered / "manuscript" / "chapter-001.md").read_text(encoding="utf-8").endswith(
        "previous manuscript."
    )
    assert (recovered / ".ember" / "story.db").read_bytes() == b"legacy-story-history"
    assert source.exists(), "Recovery must never remove the original project."


def test_recovery_is_idempotent_and_never_overwrites_existing_project(
    tmp_path: Path, monkeypatch
) -> None:
    active = tmp_path / "new-install" / "data"
    legacy_root = tmp_path / "old-install"
    _write_project(
        legacy_root,
        slug="old-novel",
        project_id="project-123",
        chapter="# Chapter 1\n\nOriginal recovered text.",
    )

    storage.DATA_ROOT = active
    storage.PROJECTS_ROOT = active / "projects"
    monkeypatch.setattr(project_recovery, "_search_roots", lambda: [legacy_root])
    monkeypatch.setattr(project_recovery, "_historical_windows_launch_roots", list)

    first = project_recovery.recover_legacy_projects()
    recovered_file = storage.PROJECTS_ROOT / "old-novel" / "manuscript" / "chapter-001.md"
    recovered_file.write_text("# Chapter 1\n\nEdited after recovery.", encoding="utf-8")
    second = project_recovery.recover_legacy_projects()

    assert first["recovered_count"] == 1
    assert second["recovered_count"] == 0
    assert any(item["reason"] == "already_present" for item in second["skipped"])
    assert recovered_file.read_text(encoding="utf-8").endswith("Edited after recovery.")


def test_recovery_restores_project_when_project_json_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
    active = tmp_path / "new-install" / "data"
    legacy_root = tmp_path / "detached-drive"
    source = _write_metadata_less_project(
        legacy_root,
        slug="lost-book",
        chapter="# Chapter 9\n\nThe manuscript survived without its metadata file.",
    )

    storage.DATA_ROOT = active
    storage.PROJECTS_ROOT = active / "projects"
    monkeypatch.setattr(project_recovery, "_search_roots", lambda: [legacy_root])
    monkeypatch.setattr(project_recovery, "_historical_windows_launch_roots", list)

    result = project_recovery.recover_legacy_projects()

    assert result["recovered_count"] == 1
    recovered = storage.PROJECTS_ROOT / "lost-book"
    metadata = json.loads((recovered / "project.json").read_text(encoding="utf-8"))
    assert metadata["slug"] == "lost-book"
    assert metadata["recovered_from"] == str(source)
    assert metadata["id"]
    assert (recovered / "manuscript" / "chapter-009.md").read_text(encoding="utf-8").endswith(
        "metadata file."
    )
    assert (recovered / ".ember" / "story.db").read_bytes() == b"older-history"
    assert not (source / "project.json").exists(), "Recovery must not modify the source folder."


def test_windows_drive_roots_are_included_in_search_roots(tmp_path: Path, monkeypatch) -> None:
    drive = tmp_path / "simulated-drive"
    drive.mkdir()
    monkeypatch.setattr(project_recovery, "_windows_drive_roots", lambda: [drive])
    monkeypatch.setattr(project_recovery, "_historical_windows_launch_roots", list)

    roots = project_recovery._search_roots()

    assert drive.resolve() in roots


def test_historical_cwd_probe_finds_pre_working_directory_fix_project(
    tmp_path: Path, monkeypatch
) -> None:
    active = tmp_path / "current" / "data"
    old_launch_cwd = tmp_path / "windows-system32-simulated"
    _write_project(
        old_launch_cwd,
        slug="cwd-book",
        project_id="cwd-project",
        chapter="# CWD Chapter\n\nSaved beneath the launcher's inherited working directory.",
    )
    storage.DATA_ROOT = active
    storage.PROJECTS_ROOT = active / "projects"
    monkeypatch.setattr(
        project_recovery,
        "_historical_windows_launch_roots",
        lambda: [old_launch_cwd],
    )

    found = project_recovery._direct_historical_projects()

    assert any(item["slug"] == "cwd-book" for item in found)
    assert any(item["discovery"] == "historical_cwd_data_root" for item in found)


def test_history_only_story_db_reconstructs_missing_manuscript(
    tmp_path: Path, monkeypatch
) -> None:
    active = tmp_path / "current" / "data"
    old_launch_cwd = tmp_path / "old-shell-cwd"
    source = _write_history_only_project(
        old_launch_cwd,
        slug="history-book",
        content="# Chapter 4\n\nThis prose survived inside the revision database.",
    )
    storage.DATA_ROOT = active
    storage.PROJECTS_ROOT = active / "projects"
    monkeypatch.setattr(project_recovery, "_search_roots", lambda: [old_launch_cwd])
    monkeypatch.setattr(
        project_recovery,
        "_historical_windows_launch_roots",
        lambda: [old_launch_cwd],
    )

    result = project_recovery.recover_legacy_projects()

    assert result["recovered_count"] == 1
    assert result["history_restored_count"] == 1
    recovered = storage.PROJECTS_ROOT / "history-book"
    chapter = recovered / "manuscript" / "chapter-004.md"
    assert chapter.read_text(encoding="utf-8").endswith("revision database.")
    assert result["recovered"][0]["history_restored"][0]["source"] == "story_db_revision"
    assert not (source / "manuscript").exists(), "Source evidence must remain untouched."


def test_snapshot_tree_reconstructs_missing_manuscript(tmp_path: Path) -> None:
    project = tmp_path / "orphaned-project"
    snapshot = project / ".ember" / "snapshots" / "20260912T120000000000Z" / "manuscript"
    snapshot.mkdir(parents=True)
    (snapshot / "chapter-007.md").write_text(
        "# Chapter 7\n\nRecovered from EmberWriter's automatic snapshot.", encoding="utf-8"
    )

    restored = project_recovery._restore_missing_manuscript_from_history(project)

    assert len(restored) == 1
    assert restored[0]["source"] == "snapshot"
    assert (project / "manuscript" / "chapter-007.md").read_text(encoding="utf-8").endswith(
        "automatic snapshot."
    )


def test_powershell_history_parser_extracts_launch_directories() -> None:
    text = """
cd C:\\Users\\Jeff\\Documents\\Writing
.\\start.ps1
Set-Location 'D:\\Code\\EmberWriter-old'
.\\start.ps1
pushd \"E:\\Archive\\Ember Writer\"
"""

    roots = project_recovery._history_location_candidates(text)

    assert roots == [
        r"C:\Users\Jeff\Documents\Writing",
        r"D:\Code\EmberWriter-old",
        r"E:\Archive\Ember Writer",
    ]
