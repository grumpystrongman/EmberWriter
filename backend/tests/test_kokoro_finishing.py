"""Source-bound neural proof, retake, and whole-book chapter export."""
from __future__ import annotations

import hashlib
import json
import wave
import zipfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import audio_production, kokoro_book, kokoro_finishing, storage
from app.main import app


def _fixture(tmp_path):
    slug = storage.create_project("Beta neural proof fixture")["slug"]
    chapters = [
        ("manuscript/001.md", "Chapter One", "Mira waited at the old bridge before dawn. She heard the river beneath the stone."),
        ("manuscript/002.md", "Chapter Two", "Night fell over the city and the captain returned with a torn chart."),
    ]
    data = audio_production.load(slug)
    data["kokoro_voices"] = {"Narrator": {"voice_id": "af_heart", "speed": 1}}
    audio_production._write(slug, data)
    for path, _, text in chapters:
        storage.save_text(slug, path, text)
    documents = [{"path": path, "title": title, "content": text}
                 for path, title, text in chapters]
    return slug, chapters, documents


def _synthetic_part(slug, job, index):
    dest = kokoro_book._part_path(slug, job["id"], index)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(bytes([index % 256, 0]) * 24000)
    return hashlib.sha256(dest.read_bytes()).hexdigest()


async def _finished(slug, docs):
    with (
        patch("app.kokoro_book.compiled_documents", return_value=docs),
        patch("app.kokoro_book.kokoro_local.status",
              return_value={"installed": True, "voice_ids": ["af_heart"]}),
        patch("app.kokoro_book._render_part", side_effect=_synthetic_part),
    ):
        job = kokoro_book.start(slug)
        while job["status"] != "completed":
            job = await kokoro_book.advance(slug)
    return job


@pytest.mark.asyncio
async def test_neural_proof_requires_full_listen_and_export_requires_all_chapters(tmp_path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug, chapters, docs = _fixture(tmp_path)
        await _finished(slug, docs)
        status = kokoro_finishing.proof_status(slug)
        assert status["total"] == 2 and not status["ready"]
        with pytest.raises(ValueError, match="proof-approve"):
            kokoro_finishing.export(slug)
        path = chapters[0][0]
        with pytest.raises(ValueError, match="full listening"):
            kokoro_finishing.approve(slug, path, 1, False, True)
        with pytest.raises(ValueError, match="complete recording"):
            kokoro_finishing.approve(slug, path, 0.01, True, True)
        for path, _, _ in chapters:
            kokoro_finishing.approve(slug, path, 1, True, True)
        assert kokoro_finishing.proof_status(slug)["ready"]
        package = kokoro_finishing.export(slug)
        assert package["chapters"] == 2 and package["format"] == "approved_wav_chapter_zip"
        assert not package["retailer_certified"]
        exported = kokoro_finishing.export_file(slug, package["filename"])
        with zipfile.ZipFile(exported) as archive:
            assert archive.namelist() == ["chapter-001.wav", "chapter-002.wav", "manifest.json"]
            metadata = json.loads(archive.read("manifest.json"))
            assert not metadata["mastered"] and not metadata["retailer_certified"]
            for row in metadata["chapters"]:
                assert hashlib.sha256(archive.read(row["file"])).hexdigest() == row["audio_sha256"]
        with TestClient(app) as client:
            response = client.get(f"/api/projects/{slug}/audiobook-production/kokoro/book/proof")
            assert response.status_code == 200 and response.json()["ready"]
            download = client.get(
                f"/api/projects/{slug}/audiobook-production/kokoro/book/export/{package['filename']}"
            )
            assert download.status_code == 200
            assert download.content == exported.read_bytes()


@pytest.mark.asyncio
async def test_retake_revokes_only_affected_chapter_and_changes_checksum(tmp_path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug, chapters, docs = _fixture(tmp_path)
        await _finished(slug, docs)
        for path, _, _ in chapters:
            kokoro_finishing.approve(slug, path, 1, True, True)
        original = kokoro_finishing.export(slug)
        called = {"n": 0}

        def different_part(slug, job, index):
            called["n"] += 1
            dest = kokoro_book._part_path(slug, job["id"], index)
            with wave.open(str(dest), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(24000)
                wav.writeframes(bytes([59, 1]) * 24000)
            return hashlib.sha256(dest.read_bytes()).hexdigest()

        with patch("app.kokoro_book._render_part", side_effect=different_part):
            response = await kokoro_finishing.retake(slug, chapters[0][0], 0)
        assert called["n"] == 1
        assert response["status"] == "retaken_unapproved"
        proof = kokoro_finishing.proof_status(slug)
        assert proof["approved"] == 1 and not proof["ready"]
        assert proof["chapters"][1]["approved"]
        with pytest.raises(ValueError, match="approval is stale"):
            kokoro_finishing.export_file(slug, original["filename"])
        kokoro_finishing.approve(slug, chapters[0][0], 1, True, True)
        assert kokoro_finishing.proof_status(slug)["ready"]


@pytest.mark.asyncio
async def test_manuscript_change_blocks_old_approved_audio_and_export(tmp_path):
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug, chapters, docs = _fixture(tmp_path)
        await _finished(slug, docs)
        for path, _, _ in chapters:
            kokoro_finishing.approve(slug, path, 1, True, True)
        package = kokoro_finishing.export(slug)
        storage.save_text(slug, chapters[0][0], "A new chapter has replaced the original source text.")
        proof = kokoro_finishing.proof_status(slug)
        assert proof["stale"] and not proof["ready"]
        with pytest.raises(ValueError, match="stale"):
            kokoro_finishing.export_file(slug, package["filename"])
        with pytest.raises(ValueError, match="changed"):
            kokoro_finishing.approve(slug, chapters[0][0], 1, True, True)


@pytest.mark.asyncio
async def test_real_ffmpeg_m4b_has_chapter_navigation_and_frozen_audio(tmp_path):
    import shutil

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("local FFmpeg unavailable")
    with patch.object(storage, "PROJECTS_ROOT", tmp_path / "projects"):
        slug, chapters, docs = _fixture(tmp_path)
        await _finished(slug, docs)
        for path, _, _ in chapters:
            kokoro_finishing.approve(slug, path, 1, True, True)
        result = kokoro_finishing.export_m4b(slug)
        assert result["chapters"] == 2
        assert result["codec"] == "aac"
        assert result["sample_rate"] == 44100
        assert not result["retailer_certified"]
        path = kokoro_finishing.m4b_file(slug, result["filename"])
        assert path.read_bytes()[4:8] == b"ftyp"
        with TestClient(app) as client:
            response = client.get(
                f"/api/projects/{slug}/audiobook-production/kokoro/book/export-m4b/"
                + result["filename"]
            )
            assert response.status_code == 200
        kokoro_finishing.revoke(slug, chapters[0][0])
        with pytest.raises(ValueError, match="approval is stale"):
            kokoro_finishing.m4b_file(slug, result["filename"])
