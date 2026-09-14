import json
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

    roots = project_recovery._search_roots()

    assert drive.resolve() in roots
