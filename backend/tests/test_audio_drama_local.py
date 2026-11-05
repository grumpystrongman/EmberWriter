"""Real local neural-TTS protocol contract, tested without contacting a model."""
from __future__ import annotations

import hashlib
import io
import json
import wave
from pathlib import Path
from unittest.mock import patch

import msgpack
import pytest
from fastapi.testclient import TestClient

from app import audio_drama, audio_production, audiobook_local, storage
from app.main import app


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def raise_for_status(self):
        pass

    def iter_bytes(self):
        yield self.data[:23]
        yield self.data[23:]


class FakeFish:
    def __init__(self, data):
        self.data = data
        self.request = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def stream(self, method, url, **kwargs):
        self.request = {"method": method, "url": url, "params": kwargs["params"],
                        "headers": kwargs["headers"],
                        "body": msgpack.unpackb(kwargs["content"], raw=False)}
        return FakeResponse(self.data)


def prepared(tmp_path):
    slug = storage.create_project("Synthetic Audio Drama")["slug"]
    path = "manuscript/scene-one.md"
    storage.save_text(slug, path, '# One\n\nMira said "We must go now." The storm approached.')
    text = audiobook_local._spoken_text(storage.read_text(slug, path))
    start = text.index('"We must go now."')
    with patch("app.audiobook_local.available_voices", return_value=["Actor A"]):
        audio_production.save_character_voice(slug, "Mira", "Actor A", 0)
        audio_production.save_cast(slug, path, start, start + len('"We must go now."'),
                                   '"We must go now."', "", "Mira")
    audio_drama.save_voice(slug, "Mira", "mira-reference", "whispered with urgency", seed=41)
    return slug, path, start


def test_local_neural_tts_rehearsal_is_explicit_source_bound_and_persistent(tmp_path: Path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug, path, start = prepared(tmp_path)
        voice = audio_drama.voice_library(slug)["Mira"]
        assert voice["seed"] == 41
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(bytes(24000))
        audio = buffer.getvalue()
        # The mock emits valid synthetic WAV data. No neural model runs.
        fake = FakeFish(audio)
        with patch("app.audio_drama.httpx.Client", return_value=fake):
            result = audio_drama.render_take(slug, path, start, 8080)
        assert result["status"] == "unapproved_rehearsal"
        assert result["character"] == "Mira"
        assert result["audio_sha256"] == hashlib.sha256(audio).hexdigest()
        assert audio_drama.take_file(slug, result["filename"]).read_bytes() == audio
        assert fake.request["url"] == "http://127.0.0.1:8080/v1/tts"
        assert fake.request["params"] == {"format": "msgpack"}
        assert fake.request["body"]["reference_id"] == "mira-reference"
        assert fake.request["body"]["seed"] == 41
        assert "[whispered with urgency]" in fake.request["body"]["text"]
        saved = json.loads((audio_drama._folder(slug) / (result["id"] + ".json")).read_text(encoding="utf-8"))
        assert saved["source_sha256"] == result["source_sha256"]
        storage.save_text(slug, path, "The line is gone; replace the voice assignment.")
        with pytest.raises(ValueError, match="changed|reassign|Dialogue"):
            audio_drama.render_take(slug, path, start)


def test_local_endpoint_and_reference_validation(tmp_path: Path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug = storage.create_project("Neural Security")["slug"]
        with pytest.raises(ValueError):
            audio_drama.save_voice(slug, "Mira", "https://outside.example/voice")
        with pytest.raises(ValueError):
            audio_drama._local_url(80)
        with pytest.raises(ValueError):
            audio_drama.take_file(slug, "../../secret.wav")
        with TestClient(app) as client:
            response = client.put(f"/api/projects/{slug}/audiobook-production/neural-voices",
                                  json={"character": "Mira", "reference_id": "mira1",
                                        "direction": "warm", "seed": 12})
            assert response.status_code == 200, response.text
            saved = client.get(f"/api/projects/{slug}/audiobook-production/neural-voices")
            assert saved.json()["Mira"]["reference_id"] == "mira1"
            invalid = client.post(f"/api/projects/{slug}/audiobook-production/neural-takes",
                                  json={"path": "manuscript/000.md", "start": 0, "port": 8080})
            assert invalid.status_code == 409


def test_binder_ordered_audio_drama_plan_keeps_source_and_cast_identity(tmp_path: Path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug, path, _start = prepared(tmp_path)
        second = "manuscript/scene-two.md"
        storage.save_text(slug, second, "Mira returned. The gathering began.")
        audio_drama.save_voice(slug, "Narrator", "narrator-main", "restrained storyteller")
        with patch("app.publishing.compiled_documents", return_value=[
            {"path": path, "title": "Opening"},
            {"path": second, "title": "Gathering"},
        ]):
            plan = audio_drama.production_plan(slug)
            assert plan["mode"] == "author_review_required"
            assert [ch["path"] for ch in plan["chapters"]] == [path, second]
            first = plan["chapters"][0]["segments"]
            assert "".join(part["text"] for part in first) == audiobook_local._spoken_text(storage.read_text(slug, path))
            assert any(part["speaker"] == "Mira" and part["reference_id"] == "mira-reference" for part in first)
            assert any(part["speaker"] == "Narrator" and part["reference_id"] == "narrator-main" for part in first)
            assert plan["warnings"] == []
            with TestClient(app) as client:
                response = client.get(f"/api/projects/{slug}/audiobook-production/neural-production-plan")
                assert response.status_code == 200, response.text
                assert len(response.json()["chapters"]) == 2
            assert all(ch["source_sha256"] == hashlib.sha256(
                storage.read_text(slug, ch["path"]).encode("utf-8")).hexdigest()
                for ch in plan["chapters"])


def test_neural_only_character_is_castable_without_windows_voice(tmp_path: Path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug = storage.create_project("Neural-Only Cast")["slug"]
        path = "manuscript/001.md"
        storage.save_text(slug, path, 'Mira looked over. "I will return soon." Everyone listened.')
        audio_production.save_character_voice(slug, "Mira", "", -1)
        audio_drama.save_voice(slug, "Mira", "authorized-mira")
        text = audiobook_local._spoken_text(storage.read_text(slug, path))
        quote = '"I will return soon."'
        start = text.index(quote)
        cast = audio_production.save_cast(slug, path, start, start + len(quote),
                                          quote, "", "Mira")
        assert cast["chapter_casts"][path][0]["character"] == "Mira"
        assert cast["chapter_casts"][path][0]["voice"] == ""
        with pytest.raises(ValueError, match="neural-only"):
            audiobook_local.render(slug, path)
        with patch("app.publishing.compiled_documents", return_value=[
            {"path": path, "title": "One"},
        ]):
            plan = audio_drama.production_plan(slug)
        assert any(segment["speaker"] == "Mira" and
                   segment["reference_id"] == "authorized-mira"
                   for segment in plan["chapters"][0]["segments"])


def test_sapi_batch_preflight_rejects_neural_only_cast_before_rendering(tmp_path: Path):
    from app import audiobook_jobs

    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug = storage.create_project("Batch neural-only guard")["slug"]
        path = "manuscript/001.md"
        storage.save_text(slug, path, 'Mira asked "Where is the door?" And waited.')
        audio_production.save_character_voice(slug, "Mira", "")
        audio_drama.save_voice(slug, "Mira", "local-mira")
        text = audiobook_local._spoken_text(storage.read_text(slug, path))
        quote = '"Where is the door?"'
        start = text.index(quote)
        audio_production.save_cast(slug, path, start, start + len(quote), quote, "", "Mira")
        with (
            patch("app.audiobook_jobs._book", return_value=[{"path": path}]),
            pytest.raises(ValueError, match="neural-only"),
        ):
            audiobook_jobs.start(slug)


def test_explicit_speaker_suggestions_require_author_approval(tmp_path: Path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug = storage.create_project("Speaker suggestions")["slug"]
        path = "manuscript/001.md"
        source = 'Mira said, "We leave now." Then no one spoke. "Why?" asked Elara. "Nobody knows."'
        storage.save_text(slug, path, source)
        audio_production.save_character_voice(slug, "Mira", "")
        audio_production.save_character_voice(slug, "Elara", "")
        audio_drama.save_voice(slug, "Mira", "ref-mira")
        audio_drama.save_voice(slug, "Elara", "ref-elara")
        candidates = audio_production.suggest_casts(slug, path)
        assert {entry["character"] for entry in candidates["suggestions"]} == {"Mira", "Elara"}
        assert candidates["unassigned_or_ambiguous"] >= 1
        assert audio_production.load(slug)["chapter_casts"] == {}
        with TestClient(app) as client:
            resp = client.get(f"/api/projects/{slug}/audiobook-production/casting-suggestions",
                              params={"path": path})
            assert resp.status_code == 200, resp.text
            assert len(resp.json()["suggestions"]) == 2
        suggestion = next(row for row in candidates["suggestions"] if row["character"] == "Mira")
        applied = audio_production.save_cast(slug, path, suggestion["start"], suggestion["end"],
                                             suggestion["text"], "", "Mira")
        assert len(applied["chapter_casts"][path]) == 1
        assert len(audio_production.suggest_casts(slug, path)["suggestions"]) == 1
