import json
from pathlib import Path

from app import project_restore, storage


def _use_temp_storage(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path / "data"
    storage.PROJECTS_ROOT = storage.DATA_ROOT / "projects"


def _metadata(name: str, slug: str, project_id: str) -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "id": project_id,
            "slug": slug,
            "name": name,
            "description": "Existing EmberWriter project",
        }
    ).encode()


def test_load_accepts_selected_data_projects_folder(tmp_path: Path) -> None:
    _use_temp_storage(tmp_path)

    result = project_restore.restore_uploaded_project(
        [
            (
                "projects/nh-ghost-story/project.json",
                _metadata("NH Ghost Story", "nh-ghost-story", "ghost-id"),
            ),
            (
                "projects/nh-ghost-story/manuscript/chapter-001.md",
                b"# Chapter 1\n\nThe original ghost story survived.",
            ),
            (
                "projects/nh-ghost-story/characters/mara.md",
                b"# Mara\n\nOriginal character notes.",
            ),
        ]
    )

    assert result["loaded_count"] == 1
    assert result["project"]["name"] == "NH Ghost Story"
    slug = result["project"]["slug"]
    root = storage.PROJECTS_ROOT / slug
    assert (root / "manuscript" / "chapter-001.md").read_text(encoding="utf-8").endswith(
        "survived."
    )
    assert (root / "characters" / "mara.md").exists()


def test_load_projects_library_restores_each_child_project(tmp_path: Path) -> None:
    _use_temp_storage(tmp_path)

    result = project_restore.restore_uploaded_project(
        [
            ("projects/book-one/project.json", _metadata("Book One", "book-one", "one-id")),
            ("projects/book-one/manuscript/chapter.md", b"# One\n\nFirst book."),
            ("projects/book-two/project.json", _metadata("Book Two", "book-two", "two-id")),
            ("projects/book-two/manuscript/chapter.md", b"# Two\n\nSecond book."),
        ]
    )

    assert result["loaded_count"] == 2
    assert {project["name"] for project in result["projects"]} == {"Book One", "Book Two"}
    assert {path.name for path in storage.PROJECTS_ROOT.iterdir() if path.is_dir()} == {
        "book-one",
        "book-two",
    }


def test_loading_current_library_project_reuses_it_instead_of_duplicating(tmp_path: Path) -> None:
    _use_temp_storage(tmp_path)
    existing = storage.create_project("NH Ghost Story", "Already in the active library")
    slug = existing["slug"]
    root = storage.PROJECTS_ROOT / slug
    metadata = (root / "project.json").read_bytes()
    chapter = (root / "manuscript" / "chapter-001.md").read_bytes()

    result = project_restore.restore_uploaded_project(
        [
            (f"projects/{slug}/project.json", metadata),
            (f"projects/{slug}/manuscript/chapter-001.md", chapter),
        ]
    )

    assert result["loaded_count"] == 1
    assert result["reused_count"] == 1
    assert result["project"]["slug"] == slug
    assert [path.name for path in storage.PROJECTS_ROOT.iterdir() if path.is_dir()] == [slug]
