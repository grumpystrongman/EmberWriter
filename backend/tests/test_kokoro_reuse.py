"""Cached spoken segments must only be reused after SHA and voice identity checks."""
import hashlib
import wave
from pathlib import Path
from unittest.mock import patch

from app import kokoro_book


def _wav(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(bytes(5000))


def test_verified_speech_reuse_is_identity_bound(tmp_path):
    def part_path(_slug, job, i):
        return tmp_path / job / f"part-{i:05d}.wav"
    oldpath = part_path("book", "old", 0)
    _wav(oldpath)
    sha = hashlib.sha256(oldpath.read_bytes()).hexdigest()
    old = {"id": "old", "engine": "kokoro-onnx", "status": "completed",
           "chunks": [{"chapter": 0, "speaker": "Mara", "text": '"Help!"',
                       "voice_id": "af_bella", "speed": 1.0, "status": "rendered",
                       "sha256": sha}]}
    same = {"chapter": 0, "speaker": "Mara", "text": '"Help!"',
            "voice_id": "af_bella", "speed": 1.0, "status": "queued"}
    changed_voice = {**same, "voice_id": "af_heart"}
    new = {"id": "new", "engine": "kokoro-onnx",
           "chunks": [same.copy(), changed_voice.copy()]}
    with patch.object(kokoro_book, "_part_path", part_path):
        count = kokoro_book._reuse_verified_speech("book", old, new)
        assert count == 1
        assert new["chunks"][0]["status"] == "rendered"
        assert new["chunks"][0]["sha256"] == sha
        assert new["chunks"][1]["status"] == "queued"
        assert part_path("book", "new", 0).read_bytes() == oldpath.read_bytes()


def test_corrupted_speech_never_reused(tmp_path):
    path = tmp_path / "old" / "part-00000.wav"
    _wav(path)
    old = {"id": "old", "engine": "kokoro-onnx", "status": "completed",
           "chunks": [{"chapter": 0, "speaker": "Mara", "text": "Hi",
                       "voice_id": "af_bella", "speed": 1.0, "status": "rendered",
                       "sha256": "0" * 64}]}
    new = {"id": "new", "engine": "kokoro-onnx",
           "chunks": [{"chapter": 0, "speaker": "Mara", "text": "Hi",
                       "voice_id": "af_bella", "speed": 1.0, "status": "queued"}]}
    with patch.object(kokoro_book, "_part_path",
                      lambda slug, job, idx: tmp_path / job / f"part-{idx:05d}.wav"):
        assert kokoro_book._reuse_verified_speech("book", old, new) == 0
        assert new["chunks"][0]["status"] == "queued"
