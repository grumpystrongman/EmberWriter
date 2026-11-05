"""Synthetic regression coverage for source-anchored dialogue casting and residual noise."""
import json
import math
import shutil
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from app import audio_production, audiobook_local, storage
from app.audio_mastering import _residual_noise
from app.proof_approval import approve, proof_status


class DialogueCastingAndProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.scope = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        self.scope.start()
        self.slug = storage.create_project("Synthetic Dialogue")[ "slug" ]
        self.path = "manuscript/chapter-001.md"
        self.chapter = '# Captain\n\nThe pilot looked up. "I have the map," said Mira. The captain agreed.'
        storage.save_text(self.slug, self.path, self.chapter)

    def tearDown(self):
        self.scope.stop()
        self.temp.cleanup()

    def _fake_sapi(self, args, **kwargs):
        if "-OutputPath" not in args:
            return None
        segments_path = Path(args[args.index("-SegmentsPath") + 1])
        self.segments = json.loads(segments_path.read_text(encoding="utf-8"))
        with wave.open(str(Path(args[args.index("-OutputPath") + 1])), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\x01\x00" * 16000)

    def test_dialogue_voice_changes_are_explicit_and_deterministic(self):
        text = audiobook_local._spoken_text(self.chapter)
        quote = '"I have the map,"'
        start = text.index(quote)
        with patch("app.audiobook_local.available_voices", return_value=["Synthetic Cast"]):
            data = audio_production.save_cast(self.slug, self.path, start, start + len(quote),
                                              quote, "Synthetic Cast")
            self.assertEqual(len(data["chapter_casts"][self.path]), 1)
            with self.assertRaisesRegex(ValueError, "overlap"):
                audio_production.save_cast(self.slug, self.path, start, start + len(quote),
                                           quote, "Synthetic Cast")
            with patch("app.audiobook_local.subprocess.run", side_effect=self._fake_sapi), patch(
                "app.audiobook_local.shutil.which", return_value=None
            ):
                rendered = audiobook_local.render(self.slug, self.path)
        self.assertEqual(rendered["source_path"], self.path)
        self.assertEqual([segment["voice"] for segment in self.segments],
                         ["", "Synthetic Cast", ""])
        self.assertEqual("".join(segment["text"] for segment in self.segments), text)
        self.assertEqual(storage.read_text(self.slug, self.path), self.chapter)
        with patch("app.audiobook_local.available_voices", return_value=["Synthetic Cast"]):
            with self.assertRaisesRegex(ValueError, "matches"):
                audio_production.save_cast(self.slug, self.path, start, start + 2,
                                           "different", "Synthetic Cast")
        with self.assertRaisesRegex(ValueError, "complete listen"):
            approve(self.slug, self.path, 1, False, True)
        with self.assertRaisesRegex(ValueError, "Full recorded duration"):
            approve(self.slug, self.path, 0.1, True, True)
        approval = approve(self.slug, self.path, 1.0, True, True)
        self.assertTrue(approval["source_aligned"])
        self.assertTrue(proof_status(self.slug, self.path, rendered["filename"])["approved"])
        with audiobook_local.audio_file(self.slug, rendered["filename"]).open("ab") as output:
            output.write(b"changed")
        self.assertFalse(proof_status(self.slug, self.path, rendered["filename"])["approved"])
        audio_production.clear_casts(self.slug, self.path)
        self.assertFalse(audio_production.snapshot(self.slug)["chapter_casts"])


@unittest.skipUnless(shutil.which("ffmpeg"), "Requires local FFmpeg for actual PCM decoding")
class ResidualNoiseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def make_wave(self, file, frequencies):
        with wave.open(str(file), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            for level, seconds in frequencies:
                samples = (struct.pack("<h", int(level * math.sin(2*math.pi*440*n/16000)))
                           for n in range(int(seconds*16000)))
                wav.writeframes(b"".join(samples))

    def test_noise_is_measured_separately_from_loud_dialogue(self):
        wav = Path(self.tmp.name) / "noise.wav"
        self.make_wave(wav, [(20, 2.0), (12000, 1.0), (20, 2.0)])
        data = _residual_noise(wav)
        self.assertEqual(data["noise_floor_status"], "estimated_residual")
        self.assertGreater(data["noise_floor_sample_seconds"], 3)
        self.assertAlmostEqual(data["noise_floor_estimate_dbfs"], -67.3, delta=4)

    def test_digital_silence_is_not_room_tone(self):
        wav = Path(self.tmp.name) / "silence.wav"
        self.make_wave(wav, [(0, 2.0), (12000, 2.0)])
        data = _residual_noise(wav)
        self.assertEqual(data["noise_floor_status"], "insufficient_quiet_samples")
        self.assertIsNone(data["noise_floor_estimate_dbfs"])
        self.assertGreaterEqual(data["digital_silence_seconds"], 1.75)


if __name__ == "__main__":
    unittest.main()
