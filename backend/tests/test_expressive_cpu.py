"""No-GPU expressive speech contract tests. No model is downloaded."""
import hashlib
from unittest.mock import patch

import pytest

from app import audio_production, kitten_local, storage
from app.expressive_prosody import PRESETS, capabilities, direction_settings


def test_emotion_mapping_does_not_claim_unsupported_kitten_tags():
    assert kitten_local.line_prompt('"Go now!"', "anger", 4) == ('[angry] "Go now!"', "expressive")
    assert kitten_local.line_prompt('"Go now!"', "neutral", 3) == ('"Go now!"', "stable")
    assert kitten_local.line_prompt("Stay.", "tenderness", 1) == ("[tender] Stay.", "stable")
    assert all(tag in {
        "", "joyful", "excited", "sad", "angry", "nervous", "tender",
        "stern", "contemplative", "surprised", "mundane",
    } for tag in kitten_local.EMOTION_TAGS.values())
    with pytest.raises(ValueError):
        kitten_local.line_prompt("Hello", "unsupported-emotion", 3)
    with pytest.raises(ValueError):
        kitten_local.line_prompt("Hello", "joy", 99)


def test_expression_presets_are_bounded_and_engine_is_honest():
    neutral = direction_settings("neutral", 3, 1.0)
    joy = direction_settings("joy", 4, 1.0)
    sadness = direction_settings("sadness", 2, 1.0)
    assert joy["speed"] > neutral["speed"]
    assert sadness["speed"] < neutral["speed"]
    assert joy["pitch_semitones"] > 0
    assert sadness["pause_after_ms"] > neutral["pause_after_ms"]
    for emotion in PRESETS:
        for energy in range(1, 6):
            settings = direction_settings(emotion, energy, 1.0)
            assert 0.7 <= settings["speed"] <= 1.4
            assert 55 <= settings["pause_after_ms"] <= 400
    assert capabilities()["native_emotion_conditioning"] is False


def test_kitten_status_never_downloads_and_requires_local_model(tmp_path, monkeypatch):
    monkeypatch.delenv("EMBERWRITER_KITTEN_MODEL_DIR", raising=False)
    assert kitten_local.model_directory() is None
    assert kitten_local.status()["auto_download"] is False
    monkeypatch.setenv("EMBERWRITER_KITTEN_MODEL_DIR", str(tmp_path / "missing"))
    assert kitten_local.status()["configured"] is False


def _project(tmp_path):
    storage.PROJECTS_ROOT = tmp_path / "projects"
    slug = storage.create_project("Kitten Expression Fixture")["slug"]
    path = "manuscript/scene.md"
    chapter = 'Mira said, "The door is open." The room remained silent.'
    storage.save_text(slug, path, chapter)
    return slug, path, chapter


def test_kitten_rehearsal_uses_author_cues_without_publishing(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    pytest.importorskip("soundfile")
    slug, path, chapter = _project(tmp_path)
    model_folder = tmp_path / "kitten-model"
    model_folder.mkdir()
    (model_folder / "config.json").write_text('{"local":true}', encoding="utf-8")
    monkeypatch.setenv("EMBERWRITER_KITTEN_MODEL_DIR", str(model_folder))
    voice = "Kiki"

    class FakeModel:
        sample_rate = 24000
        available_voices = ("Kiki",)

        def generate(self, text, voice, preset):
            assert text == '[angry] "The door is open."'
            assert voice == "Kiki"
            assert preset == "expressive"
            return np.full(2400, .10, dtype=np.float32)

    with patch.object(kitten_local, "status", return_value={"installed": True}), patch.object(
        kitten_local, "_engine", return_value=FakeModel()
    ), patch.object(kitten_local, "voice_ids", return_value=[voice]):
        kitten_local.save_profile(slug, "Mira", voice)
        from app.audio_director import load_or_compile, revise_direction, save_performance
        source = chapter
        p = storage.project_root(slug) / ".ember" / "audio-director" / "scene.performance.json"
        cue = load_or_compile(p, source, ["Mira", "Narrator"])
        dialogue = next(x for x in cue["spans"] if x["kind"] == "dialogue")
        assert dialogue["speaker"] == "Mira"
        revise_direction(cue, dialogue["start"], dialogue["end"], "anger", "firm, clipped", 4)
        save_performance(p, cue)
        result = kitten_local.render_line(slug, path, dialogue["start"])
        assert result["status"] == "unapproved_rehearsal"
        assert result["publication_approved"] is False
        assert result["emotion"] == "anger"
        assert result["audio_sha256"] == hashlib.sha256(
            kitten_local.take_file(slug, result["filename"]).read_bytes()).hexdigest()
        with pytest.raises(ValueError):
            kitten_local.take_file(slug, "../escape.wav")
        assert storage.read_text(slug, path) == chapter


@pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="FFmpeg not installed")
def test_expression_wave_audio_is_valid_and_pitch_changes(tmp_path):
    np = pytest.importorskip("numpy")
    from app.expressive_prosody import apply_expression, rubberband_available
    if not rubberband_available():
        pytest.skip("FFmpeg without Rubber Band filter")
    tone = np.sin(2 * np.pi * 220 * np.arange(24000) / 24000).astype(np.float32) * 0.20
    original = apply_expression(tone, 0, -2)
    voiced = apply_expression(tone, 0.75, -2)
    assert np.max(np.abs(original)) < .21
    assert len(voiced) > 22000
    assert np.isfinite(voiced).all()
    def peak_frequency(data):
        spectrum = np.abs(np.fft.rfft(data[:20000]))
        return np.fft.rfftfreq(20000, 1 / 24000)[np.argmax(spectrum)]
    assert peak_frequency(voiced) > peak_frequency(original) * 1.03


@pytest.mark.asyncio
async def test_complete_native_cpu_emotion_book_uses_existing_approval_gate(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    pytest.importorskip("soundfile")
    from app import kokoro_book, kokoro_finishing

    slug, path, chapter = _project(tmp_path)
    state = audio_production.load(slug)
    state["kitten_voices"] = {
        "Narrator": {"voice_id": "Bruno"},
        "Mira": {"voice_id": "Kiki"},
    }
    audio_production._write(slug, state)
    from app.audio_director import load_or_compile, revise_direction, save_performance
    cue_path = storage.project_root(slug) / ".ember" / "audio-director" / "scene.performance.json"
    cue = load_or_compile(cue_path, chapter, ["Mira", "Narrator"])
    actor = next(item for item in cue["spans"] if item["kind"] == "dialogue")
    revise_direction(cue, actor["start"], actor["end"], "joy", "excited but restrained", 4)
    save_performance(cue_path, cue)
    folder = tmp_path / "kitten-model"
    folder.mkdir()
    (folder / "config.json").write_text('{"local":true}', encoding="utf-8")
    monkeypatch.setenv("EMBERWRITER_KITTEN_MODEL_DIR", str(folder))

    calls = []

    class FakeModel:
        available_voices = ("Kiki", "Bruno")
        sample_rate = 24000

        def generate(self, text, voice, preset):
            calls.append((text, voice, preset))
            return np.full(4000, .06, dtype=np.float32)

    documents = [{"path": path, "title": "The Promise", "content": chapter}]
    with patch.object(kitten_local, "status", return_value={"installed": True}), patch.object(
        kitten_local, "voice_ids", return_value=["Kiki", "Bruno"]
    ), patch.object(kitten_local, "_engine", return_value=FakeModel()), patch(
        "app.kokoro_book.compiled_documents", return_value=documents
    ):
        batch = kokoro_book.start(slug, "kitten-tts-2")
        assert batch["engine"] == "kitten-tts-2"
        assert not batch["publication_approved"]
        while batch["status"] != "completed":
            batch = await kokoro_book.advance(slug)
        assert any(t[0].startswith("[joyful] ") and t[1] == "Kiki" and t[2] == "expressive"
                   for t in calls)
        assert all(t[1] in {"Kiki", "Bruno"} for t in calls)
        assert not kokoro_finishing.proof_status(slug)["ready"]
        recording = batch["chapters"][0]["filename"]
        assert kokoro_book.chapter_audio(slug, recording).is_file()
        assert storage.read_text(slug, path) == chapter
        # A changed local model cannot be mistaken for the approved book edition.
        (folder / "config.json").write_text('{"local":false}', encoding="utf-8")
        assert kokoro_book.status(slug)["stale"] is True


def test_narrator_delivery_survives_reload_without_changing_source(tmp_path):
    from app.audio_director import load_or_compile, revise_direction, save_performance, render_plan
    source = "The old tower held its breath. Nothing moved."
    target = tmp_path / "narrator.performance.json"
    result = load_or_compile(target, source, ["Narrator"])
    narrator = next(x for x in result["spans"] if x["kind"] == "narration")
    revise_direction(result, narrator["start"], narrator["end"],
                     "awe", "wonder-struck, slow", 4)
    save_performance(target, result)
    reopened = load_or_compile(target, source, ["Narrator"])
    assert reopened["spans"][0]["performance"]["emotion"] == "awe"
    plan = render_plan(reopened, source, {"Narrator": {"voice_id": "af_heart", "speed": 1.0}})
    assert "".join(part["source_text"] for part in plan) == source
    assert plan[0]["pause_after_ms"] > 160
