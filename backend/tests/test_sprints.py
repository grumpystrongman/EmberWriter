from pathlib import Path

import pytest

from app import sprints, storage


def use_temp_data(tmp_path: Path) -> str:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"
    return storage.create_project("Sprint Test")["slug"]


def test_sprint_persists_progress_and_history(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    path = "manuscript/chapter-001.md"

    started = sprints.start_sprint(slug, path, 100, 500, 25)
    assert started["status"] == "active"
    assert started["start_words"] == 100
    assert sprints.active_sprint(slug)["id"] == started["id"]

    finished = sprints.finish_sprint(slug, started["id"], 240, "completed")
    assert finished["status"] == "completed"
    assert finished["net_words"] == 140
    assert finished["elapsed_seconds"] >= 0
    assert sprints.active_sprint(slug) is None

    history = sprints.list_sprints(slug)
    assert history[0]["id"] == started["id"]
    assert history[0]["net_words"] == 140


def test_starting_new_sprint_cancels_existing_active_sprint(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    path = "manuscript/chapter-001.md"

    first = sprints.start_sprint(slug, path, 10, 100, 10)
    second = sprints.start_sprint(slug, path, 20, 200, 20)

    assert sprints.active_sprint(slug)["id"] == second["id"]
    history = {item["id"]: item for item in sprints.list_sprints(slug)}
    assert history[first["id"]]["status"] == "cancelled"
    assert history[second["id"]]["status"] == "active"


def test_sprint_rejects_missing_document_and_project_without_orphan_data(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    with pytest.raises(FileNotFoundError):
        sprints.start_sprint(slug, "manuscript/missing.md", 0, 100, 10)

    missing_slug = "does-not-exist"
    with pytest.raises(FileNotFoundError):
        sprints.list_sprints(missing_slug)
    assert not (storage.PROJECTS_ROOT / missing_slug).exists()
