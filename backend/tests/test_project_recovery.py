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
