"""Offline Kokoro rehearsals respect author selections, identities and release boundaries."""
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import audio_production, kokoro_local, storage
from app.main import app


def _setup(tmp_path: Path):
    slug = storage.create_project("Three Character Test")["slug"]
    path = "manuscript/first.md"
    chapter = 'The cavern was quiet. "Come closer," said Mira. A distant bell rang.'
    storage.save_text(slug, path, chapter)
    audio_production.save_character_voice(slug, "Mira", "")
    from app import audio_drama
    audio_drama.save_voice(slug, "Mira", "mira-local-identity")
    audio_production.save_cast(slug, path, chapter.index('"Come closer,"'),
                               chapter.index('"Come closer,"') + len('"Come closer,"'),
                               '"Come closer,"', "", "Mira")
    return slug, path, chapter


def test_scene_cast_voices_and_provenance_without_model(tmp_path: Path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"), patch(
        "app.kokoro_local.status", return_value={"voice_ids": ["af_heart", "bf_emma"]}
    ):
        slug, path, chapter = _setup(tmp_path)
        kokoro_local.save_profile(slug, "Narrator", "af_heart", 1.0)
        kokoro_local.save_profile(slug, "Mira", "bf_emma", 0.9)
        plan = kokoro_local.scene_plan(slug, path, 0, len(chapter))
        assert [item["speaker"] for item in plan["segments"]] == ["Narrator", "Mira", "Narrator"]
        assert "".join(segment["text"] for segment in plan["segments"]) == chapter
        assert [item["voice_id"] for item in plan["segments"]] == ["af_heart", "bf_emma", "af_heart"]
        assert kokoro_local.library(slug)["Mira"]["speed"] == 0.9
        assert plan["human_review_required"]
        old_hash = plan["plan_sha256"]
        kokoro_local.save_profile(slug, "Mira", "bf_emma", 1.1)
        assert kokoro_local.scene_plan(slug, path, 0, len(chapter))["plan_sha256"] != old_hash
        with TestClient(app) as client:
            result = client.post(f"/api/projects/{slug}/audiobook-production/kokoro/scene-plan",
                                 json={"path": path, "start": 0, "end": len(chapter)})
            assert result.status_code == 200, result.text
            assert len(result.json()["segments"]) == 3


def test_rehearsal_is_unapproved_real_wav_and_cannot_escape_project(tmp_path: Path):
    # Runtime extras are optional in a standard author-only install.
    np = pytest.importorskip("numpy")
    pytest.importorskip("soundfile")

    class SyntheticKokoro:
        def __init__(self):
            self.calls = []

        def create(self, text, voice, speed, lang):
            self.calls.append((text, voice, speed, lang))
            return np.full(12000, 0.01, dtype=np.float32), 24000

    engine = SyntheticKokoro()
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"), patch(
        "app.kokoro_local.status", return_value={"installed": True, "voice_ids": ["af_heart", "bf_emma"]}
    ), patch("app.kokoro_local._engine", return_value=engine):
        slug, path, chapter = _setup(tmp_path)
        kokoro_local.save_profile(slug, "Narrator", "af_heart")
        kokoro_local.save_profile(slug, "Mira", "bf_emma")
        record = kokoro_local.render_scene(slug, path, 0, len(chapter))
        assert len(engine.calls) == 3
        assert record["status"] == "unapproved_rehearsal"
        assert not record["publication_approved"]
        assert record["seconds"] > 1.5
        file = kokoro_local.rehearsal_file(slug, record["filename"])
        assert file.read_bytes().startswith(b"RIFF")
        assert record["filename"].endswith(".wav")
        with pytest.raises(ValueError):
            kokoro_local.rehearsal_file(slug, "../secret.wav")
        with pytest.raises(ValueError, match="split"):
            start = chapter.index('"Come closer,"') + 1
            kokoro_local.scene_plan(slug, path, start, len(chapter))
        # A new manuscript revision cannot silently inherit the original scene.
        storage.save_text(slug, path, "A different story replaced the whole passage.")
        with pytest.raises(ValueError):
            kokoro_local.scene_plan(slug, path, 0, len(chapter))


def test_missing_cast_voice_and_missing_weights_are_explicit(tmp_path: Path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"), patch(
        "app.kokoro_local.status", return_value={"installed": False, "voice_ids": ["af_heart"]}
    ):
        slug, path, chapter = _setup(tmp_path)
        kokoro_local.save_profile(slug, "Narrator", "af_heart")
        with pytest.raises(ValueError, match="Mira"):
            kokoro_local.scene_plan(slug, path, 0, len(chapter))
        with pytest.raises(ValueError, match="voice"):
            kokoro_local.save_profile(slug, "Mira", "malicious_voice")


def test_kokoro_only_voice_profiles_count_toward_author_readiness(tmp_path: Path):
    from app import audio_drama

    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"), patch(
        "app.kokoro_local.status",
        return_value={"installed": True, "voice_ids": ["af_heart", "bf_emma"]},
    ):
        slug, path, _chapter = _setup(tmp_path)
        kokoro_local.save_profile(slug, "Narrator", "af_heart")
        kokoro_local.save_profile(slug, "Mira", "bf_emma")
        with patch("app.publishing.compiled_documents", return_value=[{
            "path": path, "title": "Scene"
        }]):
            readiness = audio_drama.production_readiness(slug)
            assert readiness["chapters_missing_voice_references"] == 0
            assert readiness["neural_plan_ready_chapters"] == 1
            assert readiness["proof_approved_recordings"] == 0
            assert not readiness["publication_ready"]
            plan = audio_drama.production_plan(slug)
            assert plan["warnings"] == []
            assert plan["kokoro_voice_library"]["Mira"]["voice_id"] == "bf_emma"
            assert len(plan["chapters"][0]["segments"]) == 3
