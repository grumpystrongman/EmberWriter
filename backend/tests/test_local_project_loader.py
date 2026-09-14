import json
from pathlib import Path

from app import local_project_loader, storage


def _use_temp_storage(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path / "active-data"
    storage.PROJECTS_ROOT = storage.DATA_ROOT / "projects"


def _write_project(root: Path, *, name: str, slug: str, project_id: str, prose: str) -> None:
    (root / "manuscript").mkdir(parents=True, exist_ok=True)
    (root / "characters").mkdir(parents=True, exist_ok=True)
    (root / "project.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": project_id,
                "slug": slug,
                "name": name,
                "description": "Original EmberWriter project",
                "created_at": "2026-09-11T12:00:00+00:00",
                "updated_at": "2026-09-14T12:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (root / "manuscript" / "chapter-001.md").write_text(prose, encoding="utf-8")
    (root / "characters" / "lead.md").write_text("# Lead\n\nOriginal notes.", encoding="utf-8")


def test_load_projects_from_local_library_path_copies_valid_projects(tmp_path: Path) -> None:
    _use_temp_storage(tmp_path)
    source_library = tmp_path / "old-install" / "data" / "projects"
    source = source_library / "nh-ghost-story"
    _write_project(
        source,
        name="NH Ghost Story",
        slug="nh-ghost-story",
        project_id="ghost-id",
        prose="# Chapter 1\n\nThe original manuscript is here.",
    )

    result = local_project_loader.load_projects_from_path(str(source_library))

    assert result["loaded_count"] == 1
    assert result["copied_count"] == 1
    assert result["project"]["name"] == "NH Ghost Story"
    copied = storage.PROJECTS_ROOT / result["project"]["slug"]
    assert (copied / "manuscript" / "chapter-001.md").read_text(encoding="utf-8").endswith(
        "The original manuscript is here."
    )
    assert (copied / "characters" / "lead.md").exists()
    assert source.exists()


def test_load_active_projects_root_reuses_existing_project_without_duplicate(tmp_path: Path) -> None:
    _use_temp_storage(tmp_path)
    source = storage.PROJECTS_ROOT / "nh-ghost-story"
    _write_project(
        source,
        name="NH Ghost Story",
        slug="nh-ghost-story",
        project_id="ghost-id",
        prose="# Chapter 1\n\nStill here.",
    )

    result = local_project_loader.load_projects_from_path(str(storage.PROJECTS_ROOT))

    assert result["loaded_count"] == 1
    assert result["reused_count"] == 1
    assert result["copied_count"] == 0
    assert result["project"]["slug"] == "nh-ghost-story"
    assert [path.name for path in storage.PROJECTS_ROOT.iterdir() if path.is_dir()] == [
        "nh-ghost-story"
    ]


def test_load_data_root_discovers_nested_projects_library(tmp_path: Path) -> None:
    _use_temp_storage(tmp_path)
    old_data = tmp_path / "old-install" / "data"
    _write_project(
        old_data / "projects" / "book-one",
        name="Book One",
        slug="book-one",
        project_id="one-id",
        prose="# One\n\nRecovered.",
    )
    _write_project(
        old_data / "projects" / "book-two",
        name="Book Two",
        slug="book-two",
        project_id="two-id",
        prose="# Two\n\nRecovered too.",
    )

    result = local_project_loader.load_projects_from_path(str(old_data))

    assert result["loaded_count"] == 2
    assert {project["name"] for project in result["projects"]} == {"Book One", "Book Two"}


def test_load_local_path_rejects_folder_without_emberwriter_projects(tmp_path: Path) -> None:
    _use_temp_storage(tmp_path)
    empty = tmp_path / "not-a-project"
    empty.mkdir()

    try:
        local_project_loader.load_projects_from_path(str(empty))
    except ValueError as exc:
        assert "No EmberWriter project" in str(exc)
    else:
        raise AssertionError("Expected ValueError for a non-project folder")
