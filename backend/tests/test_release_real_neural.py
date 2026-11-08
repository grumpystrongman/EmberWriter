"""Opt-in genuine Kokoro neural 20-chapter *short-prose* audiobook exercise.

Runs only with EMBER_RELEASE_REAL_NEURAL=1, a preinstalled local model, and
synthetic source. It is NOT a 60k-word audiobook or proof-listening substitute.
"""
from __future__ import annotations

import math
import os
import struct
import wave

import pytest

from app import audio_production, kokoro_book, storage
from app.binder import sync_binder


@pytest.mark.asyncio
async def test_twenty_real_cpu_neural_chapters_have_audible_waveform_and_provenance(
    tmp_path, monkeypatch,
):
    if os.environ.get("EMBER_RELEASE_REAL_NEURAL") != "1":
        pytest.skip("Only explicitly requested full neural model integration runs")
    if not kokoro_book.kokoro_local.status()["installed"]:
        pytest.skip("No existing local Kokoro ONNX model installed; never auto-download")
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "qa-projects")
    slug = storage.create_project("Real CPU Neural 20 Chapter QA")["slug"]
    # The initial seed is replaced with a tiny synthetic first chapter.
    for index in range(1, 21):
        path = ("manuscript/chapter-001.md" if index == 1
                else f"manuscript/chapter-{index:03d}.md")
        storage.save_text(
            slug, path,
            f"# The Test Lantern {index:02d}\n\n"
            f"At the old harbor, the lantern keeper remembered chapter {index}. "
            "The voice echoed beyond the tower, and the dawn returned.",
        )
    sync_binder(slug)
    cast = audio_production.load(slug)
    cast["kokoro_voices"] = {"Narrator": {"voice_id": "af_heart", "speed": 1.0}}
    audio_production._write(slug, cast)
    started = kokoro_book.start(slug)
    assert len(started["chapters"]) == 20
    assert started["total"] >= 20
    for _ in range(started["total"] + 1):
        started = await kokoro_book.advance(slug)
        if started["status"] == "completed":
            break
    assert started["status"] == "completed"
    assert started["completed"] == started["total"]
    assert not started["publication_approved"]
    lengths = []
    for entry in started["chapters"]:
        path = kokoro_book.chapter_audio(slug, entry["filename"])
        with wave.open(str(path), "rb") as recording:
            assert recording.getnchannels() == 1
            assert recording.getframerate() >= 16000
            frames = recording.readframes(recording.getnframes())
            samples = struct.unpack("<" + "h" * (len(frames) // 2), frames)
            assert samples
            energy = math.sqrt(sum(value * value for value in samples) / len(samples))
            assert energy > 30, "Real neural waveform is unexpectedly silent"
            lengths.append(len(samples) / recording.getframerate())
    assert len(lengths) == 20
    assert all(seconds > 1 for seconds in lengths)
    print("REAL_KOKORO_CHAPTERS=20 TOTAL_SPEECH_SECONDS=", round(sum(lengths), 1))
