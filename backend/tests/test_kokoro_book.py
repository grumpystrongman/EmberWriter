"""Neural whole-book batch: exact voice identity, resume, provenance and author review."""
import hashlib
import wave
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import audio_production, kokoro_book, storage
from app.main import app


def _project(tmp_path: Path):
    slug = storage.create_project("Synthetic Book for Independent Authors")["slug"]
    sources = [
        ("manuscript/first.md", 'Mira said, "Follow me." The sun set and the old bridge was quiet. ' * 9),
        ("manuscript/second.md", 'The captain watched the mountains and listened to Mira. ' * 10),
    ]
    for path, text in sources:
        storage.save_text(slug, path, text)
    audio_production.save_character_voice(slug, "Mira", "")
    # A voice identity can be Kokoro-only; no Windows SAPI binding required.
    data = audio_production.load(slug)
    data["kokoro_voices"] = {
        "Narrator": {"voice_id": "af_heart", "speed": 1.0},
        "Mira": {"voice_id": "bf_emma", "speed": 0.85},
    }
    audio_production._write(slug, data)
    first = sources[0][1]
    quote = '"Follow me."'
    pos = first.index(quote)
    audio_production.save_cast(slug, sources[0][0], pos, pos + len(quote), quote, "", "Mira")
    documents = [{"path": path, "title": f"Chapter {i + 1}", "content": text}
                 for i, (path, text) in enumerate(sources)]
    return slug, sources, documents


def _fake_render(slug, job, index):
    target = kokoro_book._part_path(slug, job["id"], index)
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(24000)
        out.writeframes(bytes(12000))
    return hashlib.sha256(target.read_bytes()).hexdigest()


@pytest.mark.asyncio
async def test_neural_batch_resumes_increments_and_assembles_unapproved_chapters(tmp_path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug, _sources, documents = _project(tmp_path)
        with (
            patch("app.kokoro_book.compiled_documents", return_value=documents),
            patch("app.kokoro_book.kokoro_local.status", return_value={"installed": True, "voice_ids": ["af_heart", "bf_emma"]}),
            patch("app.kokoro_book._render_part", side_effect=_fake_render),
        ):
            state = kokoro_book.start(slug)
            assert state["total"] > 2
            assert state["completed"] == 0
            first_job = state["id"]
            with pytest.raises(ValueError, match="unfinished"):
                kokoro_book.start(slug)
            state = await kokoro_book.advance(slug)
            assert state["completed"] == 1
            # Emulate a server restart: no in-memory task registry is needed.
            assert kokoro_book.status(slug)["id"] == first_job
            while state["status"] != "completed":
                state = await kokoro_book.advance(slug)
            assert state["completed"] == state["total"]
            assert all(ch["status"] == "rendered_unapproved" for ch in state["chapters"])
            assert not state["publication_approved"]
            for ch in state["chapters"]:
                audio = kokoro_book.chapter_audio(slug, ch["filename"])
                assert audio.is_file()
                with wave.open(str(audio), "rb") as wav:
                    assert wav.getframerate() == 24000
                    assert wav.getnframes() > 0
            with pytest.raises(ValueError):
                kokoro_book.chapter_audio(slug, "../secret.wav")


@pytest.mark.asyncio
async def test_neural_batch_stops_when_source_or_voice_is_edited(tmp_path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug, sources, documents = _project(tmp_path)
        with (
            patch("app.kokoro_book.compiled_documents", return_value=documents),
            patch("app.kokoro_book.kokoro_local.status", return_value={"installed": True, "voice_ids": ["af_heart", "bf_emma"]}),
            patch("app.kokoro_book._render_part", side_effect=_fake_render),
        ):
            kokoro_book.start(slug)
            await kokoro_book.advance(slug)
            original = kokoro_book.status(slug)["completed"]
            storage.save_text(slug, sources[1][0], "Changed manuscript after beginning the job.")
            assert kokoro_book.status(slug)["stale"]
            with pytest.raises(ValueError, match="manuscript changed"):
                await kokoro_book.advance(slug)
            assert kokoro_book.status(slug)["completed"] == original
            storage.save_text(slug, sources[1][0], sources[1][1])
            data = audio_production.load(slug)
            data["kokoro_voices"]["Mira"]["speed"] = 1.2
            audio_production._write(slug, data)
            assert kokoro_book.status(slug)["stale"]
            with pytest.raises(ValueError, match="settings changed"):
                await kokoro_book.advance(slug)


def test_chunk_planning_preserves_whitespace_and_all_voices(tmp_path):
    long_text = ("A quiet sentence. " * 160) + 'Mira said, "Go."'
    chunks = kokoro_book._split(long_text)
    assert len(chunks) >= 5
    assert "".join(chunks) == long_text
    assert all(len(part) <= kokoro_book.CHUNK_CHARS for part in chunks)
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug, _sources, documents = _project(tmp_path)
        with (
            patch("app.kokoro_book.compiled_documents", return_value=documents),
            patch("app.kokoro_book.kokoro_local.status", return_value={"installed": True, "voice_ids": ["af_heart", "bf_emma"]}),
            TestClient(app) as client,
        ):
            result = client.post(f"/api/projects/{slug}/audiobook-production/kokoro/book")
            assert result.status_code == 200, result.text
            state = client.get(f"/api/projects/{slug}/audiobook-production/kokoro/book")
            assert state.status_code == 200
            assert state.json()["total"] > 2
            assert "Follow me" not in state.text


def test_neural_batch_respects_local_author_pronunciation_dictionary(tmp_path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug, sources, docs = _project(tmp_path)
        audio_production.save_pronunciation(slug, "Mira", "MEE-rah")
        with (
            patch("app.kokoro_book.compiled_documents", return_value=docs),
            patch("app.kokoro_book.kokoro_local.status",
                  return_value={"installed": True, "voice_ids": ["af_heart", "bf_emma"]}),
        ):
            state = kokoro_book.start(slug)
            assert state["completed"] == 0
            job = kokoro_book._read(slug)
            assert any("MEE-rah" in part["text"] for part in job["chunks"])
            assert "MEE-rah" not in storage.read_text(slug, sources[0][0])


@pytest.mark.asyncio
async def test_markdown_chapter_heading_gets_distinct_voice_turn_and_real_pause(tmp_path):
    from app.audiobook_local import _spoken_text

    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug = storage.create_project("Title Pause and Buoy Pronunciation Test")["slug"]
        path = "manuscript/buoy.md"
        raw = "# The Bell Below Low Water\n\nThe buoys drifted close to the quay. A buoy struck the rock at dawn."
        storage.save_text(slug, path, raw)
        state = audio_production.load(slug)
        state["kokoro_voices"] = {"Narrator": {"voice_id": "af_heart", "speed": 1.0}}
        audio_production._write(slug, state)
        audio_production.save_pronunciation(slug, "buoys", "boo-eez")
        audio_production.save_pronunciation(slug, "buoy", "boo-ee")
        docs = [{"path": path, "title": "The Bell Below Low Water"}]
        with (
            patch("app.kokoro_book.compiled_documents", return_value=docs),
            patch("app.kokoro_book.kokoro_local.status",
                  return_value={"installed": True, "voice_ids": ["af_heart"]}),
            patch("app.kokoro_book._render_part", side_effect=_fake_render),
        ):
            status = kokoro_book.start(slug)
            job = kokoro_book._read(slug)
            first, body = job["chunks"][0], job["chunks"][1]
            assert first["text"] == "The Bell Below Low Water"
            assert first["pause_after_ms"] >= 1000
            assert "boo-eez" in body["text"] and "boo-ee" in body["text"]
            assert _spoken_text(raw).startswith(first["text"] + "\n\n")
            assert "buoys" in storage.read_text(slug, path)
            while status["status"] != "completed":
                status = await kokoro_book.advance(slug)
            audio = kokoro_book.chapter_audio(slug, status["chapters"][0]["filename"])
            with wave.open(str(audio), "rb") as complete:
                # Two synthetic 0.25-sec segments, with >=1-sec title pause.
                assert complete.getnframes() >= 2 * 6000 + 24000


@pytest.mark.asyncio
async def test_restart_assembles_chapters_when_every_audio_chunk_is_already_on_disk(tmp_path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug, _sources, documents = _project(tmp_path)
        with (
            patch("app.kokoro_book.compiled_documents", return_value=documents),
            patch("app.kokoro_book.kokoro_local.status",
                  return_value={"installed": True, "voice_ids": ["af_heart", "bf_emma"]}),
        ):
            kokoro_book.start(slug)
            job = kokoro_book._read(slug)
            for index, chunk in enumerate(job["chunks"]):
                chunk["sha256"] = _fake_render(slug, job, index)
                chunk["status"] = "rendered"
            # Simulates crash after chunks were safely committed but before
            # chapter assembly. Rerendering the complete book is forbidden.
            kokoro_book._atomic_json(kokoro_book._jobfile(slug), job)
            with patch("app.kokoro_book._render_part", side_effect=AssertionError("rerendered")):
                completed = await kokoro_book.advance(slug)
            assert completed["status"] == "completed"
            assert all(ch["status"] == "rendered_unapproved"
                       for ch in completed["chapters"])
            assert all(kokoro_book.chapter_audio(slug, chapter["filename"]).is_file()
                       for chapter in completed["chapters"])
