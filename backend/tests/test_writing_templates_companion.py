"""Genre/format choices and per-question manuscript privacy contract."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import routes_companion, storage
from app.main import app
from app.writing_templates import catalog, create, preview


@pytest.fixture
def writer_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    return storage.create_project("The Lighthouse Keeper")["slug"]


def test_template_catalog_includes_multiple_genres_and_distinct_forms() -> None:
    templates = catalog()
    choices = {row["id"] for row in templates}
    assert {"horror-novel", "science-fiction-novel", "short-story",
            "personal-essay", "academic-essay", "screenplay", "stage-play"}.issubset(choices)
    screenplay = preview("screenplay", "The Invention")
    stage = preview("stage-play", "The Invention")
    academic = preview("academic-essay", "The Invention")
    assert "INT. LOCATION - DAY" in screenplay["content"]
    assert "ACT I" in stage["content"]
    assert "Counterargument" in academic["content"]
    assert "[CITATION NEEDED]" in academic["guide"]
    assert screenplay["content"] != stage["content"]


def test_template_creation_does_not_overwrite_existing_files(writer_project: str) -> None:
    a = create(writer_project, "horror-novel", "The Last Door")
    b = create(writer_project, "horror-novel", "The Last Door")
    assert a["path"] != b["path"]
    assert storage.read_text(writer_project, a["path"]).startswith("# The Last Door")
    assert storage.read_text(writer_project, a["guide_path"]).startswith("# Writing guide: Horror")
    assert storage.read_text(writer_project, "style/author-profile.md").startswith("# Author Profile")
    context, sources = storage.compile_context(writer_project, prompt="the dark room", active_file=a["path"])
    assert a["guide_path"] in sources
    assert "Build unease" in context
    context2, sources2 = storage.compile_context(writer_project, active_file="manuscript/chapter-001.md")
    assert a["guide_path"] not in sources2
    assert "Build unease" not in context2


def test_template_api_preview_and_create(writer_project: str) -> None:
    with TestClient(app) as client:
        listing = client.get("/api/writing-templates")
        assert listing.status_code == 200
        sample = client.post("/api/writing-templates/preview",
                             json={"template_id": "stage-play", "title": "The Room"})
        assert sample.status_code == 200
        response = client.post(f"/api/projects/{writer_project}/writing-templates",
                               json={"template_id": "stage-play", "title": "The Room"})
        assert response.status_code == 201
        assert response.json()["format"] == "stage_play"
        assert client.post("/api/writing-templates/preview",
                           json={"template_id": "invalid", "title": "No"}).status_code == 400


@pytest.mark.asyncio
async def test_book_aware_companion_requires_each_question_opt_in(writer_project: str,
                                                               monkeypatch: pytest.MonkeyPatch) -> None:
    storage.save_text(writer_project, "manuscript/chapter-001.md",
                      "# Chapter 1\n\nLIORA_SECRET_SUNFLOWER opened the hidden door.")
    seen = []

    async def fake_generate(config, messages, **kwargs):
        seen.append(messages)
        return "The character opened the door [SOURCE 1]."

    monkeypatch.setattr(routes_companion, "generate", fake_generate)
    payload = routes_companion.CompanionQuestion(
        question="What happened to LIORA_SECRET_SUNFLOWER?", model="small-local")
    no_permission = await routes_companion.ask_companion(writer_project, payload)
    assert no_permission["sources"] == []
    assert "LIORA_SECRET_SUNFLOWER opened" not in str(seen[0])
    assert no_permission["read_only"]

    allowed = await routes_companion.ask_companion(writer_project,
        routes_companion.CompanionQuestion(
            question="What happened to LIORA_SECRET_SUNFLOWER?",
            model="small-local", include_writing=True))
    assert allowed["sources"]
    assert any("LIORA_SECRET_SUNFLOWER" in row["excerpt"] for row in allowed["sources"])
    assert "LIORA_SECRET_SUNFLOWER opened" in str(seen[1])
    assert storage.read_text(writer_project, "manuscript/chapter-001.md").endswith("hidden door.")


def test_offline_companion_context_cannot_return_passages_without_permission(writer_project: str) -> None:
    storage.save_text(writer_project, "manuscript/chapter-001.md", "# Book\n\nVIOLET_CONTEXT_SENTINEL")
    with TestClient(app) as client:
        plain = client.get(f"/api/projects/{writer_project}/companion/context",
                           params={"question": "VIOLET_CONTEXT_SENTINEL"})
        assert plain.status_code == 200
        assert plain.json()["sources"] == []
        assert "VIOLET_CONTEXT_SENTINEL" not in str(plain.json())
        with_permission = client.get(f"/api/projects/{writer_project}/companion/context",
                                     params={"question": "VIOLET_CONTEXT_SENTINEL",
                                             "include_writing": True})
        assert with_permission.status_code == 200
        assert with_permission.json()["sources"]
