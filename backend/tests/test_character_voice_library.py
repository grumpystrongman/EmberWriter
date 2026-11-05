"""Project voice bible persistence and cross-chapter casting regression."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import audio_production, audiobook_local, storage
from app.main import app


def test_character_voice_library_reuses_identity_and_updates_all_chapters(tmp_path: Path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"), patch(
        "app.audiobook_local.available_voices", return_value=["Actor A", "Actor B"]
    ):
        slug = storage.create_project("Synthetic Voice Continuity")["slug"]
        paths = ["manuscript/001.md", "manuscript/002.md"]
        for index, path in enumerate(paths, 1):
            storage.save_text(slug, path, f'Chapter {index}. Mira whispered, "Follow me." Then all went quiet.')
        audio_production.save_character_voice(slug, "Mira", "Actor A", 2)
        before = audio_production.snapshot(slug)["signature"]
        for path in paths:
            text = audiobook_local._spoken_text(storage.read_text(slug, path))
            quote = '"Follow me."'
            start = text.index(quote)
            audio_production.save_cast(slug, path, start, start + len(quote), quote, "", "Mira")
        persisted = audio_production.load(slug)
        assert persisted["character_voices"]["Mira"] == {"voice": "Actor A", "rate": 2}
        for path in paths:
            spans = persisted["chapter_casts"][path]
            assert spans[0]["voice"] == "Actor A"
            assert spans[0]["rate"] == 2
            segments = audio_production.cast_segments(
                audiobook_local._spoken_text(storage.read_text(slug, path)), spans, "Narrator", []
            )
            assert next(item for item in segments if item["voice"] == "Actor A")["rate"] == 2
        audio_production.save_character_voice(slug, "Mira", "Actor B", -2)
        after = audio_production.snapshot(slug)
        assert after["signature"] != before
        assert all(after["chapter_casts"][path][0]["voice"] == "Actor B" for path in paths)
        assert all(after["chapter_casts"][path][0]["rate"] == -2 for path in paths)
        with pytest.raises(ValueError, match="Remove existing"):
            audio_production.delete_character_voice(slug, "Mira")
        for path in paths:
            audio_production.clear_casts(slug, path)
        audio_production.delete_character_voice(slug, "Mira")
        assert audio_production.load(slug)["character_voices"] == {}


def test_named_character_voice_api_round_trip(tmp_path: Path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"), patch(
        "app.audiobook_local.available_voices", return_value=["Actor A"]
    ):
        slug = storage.create_project("Voice API")["slug"]
        with TestClient(app) as client:
            response = client.put(f"/api/projects/{slug}/audiobook-production/characters", json={
                "character": "Elara", "voice": "Actor A", "rate": 1
            })
            assert response.status_code == 200, response.text
            current = client.get(f"/api/projects/{slug}/audiobook-production")
            assert current.json()["character_voices"]["Elara"]["voice"] == "Actor A"
            removed = client.delete(f"/api/projects/{slug}/audiobook-production/characters", params={"character": "Elara"})
            assert removed.status_code == 200
