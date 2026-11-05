"""The author's desk must reflect real manuscript, voice and approval state."""
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import audio_drama, audio_production, storage
from app.main import app


def test_production_desk_is_author_first_and_cannot_approve_unrendered_audio(tmp_path: Path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug = storage.create_project("Author Production Desk")["slug"]
        path1 = "manuscript/001.md"
        path2 = "manuscript/002.md"
        storage.save_text(slug, path1, 'Mira said, "We have to go now." Then everyone departed.')
        storage.save_text(slug, path2, 'The long road to the mountain continued. This is a new chapter.')
        with patch("app.publishing.compiled_documents", return_value=[
            {"path": path1, "title": "Opening"},
            {"path": path2, "title": "Journey"},
        ]):
            report = audio_drama.production_readiness(slug)
            assert report["total_chapters"] == 2
            assert report["total_words"] > 10
            assert report["neural_plan_ready_chapters"] == 0
            assert report["chapters_missing_voice_references"] == 2
            assert report["sapi_recorded_chapters"] == 0
            assert report["proof_approved_recordings"] == 0
            assert report["publication_ready"] is False
            assert report["chapters"][0]["recording_proof_approved"] is False
            assert any("author" in step.lower() for step in report["next_steps"])
            audio_drama.save_voice(slug, "Narrator", "my-authorized-narrator")
            report = audio_drama.production_readiness(slug)
            # The quote belongs to Mira, not the narrator. Audio Director now
            # requires a matching character voice before calling it ready.
            assert report["neural_plan_ready_chapters"] == 1
            assert report["chapters_missing_voice_references"] == 1
            audio_drama.save_voice(slug, "Mira", "my-authorized-mira")
            report = audio_drama.production_readiness(slug)
            assert report["neural_plan_ready_chapters"] == 2
            assert report["chapters_missing_voice_references"] == 0
            assert report["proof_approved_recordings"] == 0
            assert report["publication_ready"] is False
            with TestClient(app) as client:
                endpoint = f"/api/projects/{slug}/audiobook-production/production-readiness"
                # Patching the document compiler affects the API as well.
                response = client.get(endpoint)
                assert response.status_code == 200, response.text
                assert response.json()["total_chapters"] == 2


def test_character_casts_trigger_missing_voice_warning_without_autogeneration(tmp_path: Path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug = storage.create_project("Missing Cast Reference")["slug"]
        path = "manuscript/first.md"
        text = 'Mira said "The storm is here." The sky was dark.'
        storage.save_text(slug, path, text)
        audio_production.save_character_voice(slug, "Mira", "")
        audio_drama.save_voice(slug, "Mira", "mira-consented")
        from app.audiobook_local import _spoken_text

        spoken = _spoken_text(text)
        phrase = '"The storm is here."'
        start = spoken.index(phrase)
        audio_production.save_cast(slug, path, start, start + len(phrase), phrase, "", "Mira")
        with patch("app.publishing.compiled_documents", return_value=[
            {"path": path, "title": "First"},
        ]):
            result = audio_drama.production_readiness(slug)
            assert result["dialogue_selections"] == 1
            assert result["chapters"][0]["missing_neural_references"] == ["Narrator"]
            assert not result["chapters"][0]["neural_drama_ready_for_rehearsal"]
            audio_drama.save_voice(slug, "Narrator", "narrator-consented")
            result = audio_drama.production_readiness(slug)
            assert result["chapters"][0]["neural_drama_ready_for_rehearsal"]
            assert not result["chapters"][0]["recording_proof_approved"]
