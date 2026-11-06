from pathlib import Path

import pytest
from fastapi import HTTPException

from app import routes_companion, storage
from app.routes_companion import CompanionQuestion


def isolated_project(tmp_path: Path) -> str:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"
    return storage.create_project("Companion Fixture")["slug"]


@pytest.mark.asyncio
async def test_companion_is_read_only_and_sends_no_manuscript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    slug = isolated_project(tmp_path)
    storage.save_text(slug, "manuscript/chapter.md", "PRIVATE MANUSCRIPT SENTINEL")
    messages_seen = []

    async def fake_generate(config, messages, **kwargs):
        assert config.provider == "ollama"
        assert config.base_url == "http://127.0.0.1:11434"
        messages_seen.extend(messages)
        return "Open Plan to draft a book."

    monkeypatch.setattr(routes_companion, "generate", fake_generate)
    result = await routes_companion.ask_companion(slug, CompanionQuestion(
        question="How can I plan my book?", workspace="plan", model="tiny-local"
    ))
    assert result["read_only"] is True
    assert result["mode"] == "local_ai"
    assert "PRIVATE MANUSCRIPT SENTINEL" not in str(messages_seen)
    assert storage.read_text(slug, "manuscript/chapter.md") == "PRIVATE MANUSCRIPT SENTINEL"


@pytest.mark.asyncio
async def test_companion_requires_explicit_model(tmp_path: Path) -> None:
    slug = isolated_project(tmp_path)
    with pytest.raises(HTTPException) as exc:
        await routes_companion.ask_companion(slug, CompanionQuestion(question="What next?"))
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_companion_unknown_project(tmp_path: Path) -> None:
    isolated_project(tmp_path)
    with pytest.raises(HTTPException) as exc:
        await routes_companion.ask_companion("missing", CompanionQuestion(question="What next?", model="local"))
    assert exc.value.status_code == 404
