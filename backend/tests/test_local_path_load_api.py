import json
from pathlib import Path

from fastapi.testclient import TestClient

from app import storage
from app.main import app


def _write_project(root: Path) -> None:
    (root / "manuscript").mkdir(parents=True, exist_ok=True)
    (root / "project.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "ghost-id",
                "slug": "nh-ghost-story",
                "name": "NH Ghost Story",
                "description": "Existing project",
                "created_at": "2026-09-11T12:00:00+00:00",
                "updated_at": "2026-09-14T12:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (root / "manuscript" / "chapter-001.md").write_text(
        "# Chapter 1\n\nStill here.", encoding="utf-8"
    )


def test_load_path_api_loads_projects_library_from_disk(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path / "active-data"
    storage.PROJECTS_ROOT = storage.DATA_ROOT / "projects"
    source_library = tmp_path / "old-data" / "projects"
    _write_project(source_library / "nh-ghost-story")

    response = TestClient(app).post(
        "/api/projects/load-path",
        json={"source_path": str(source_library)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["loaded_count"] == 1
    assert body["project"]["name"] == "NH Ghost Story"
    assert (storage.PROJECTS_ROOT / "nh-ghost-story" / "manuscript" / "chapter-001.md").exists()
