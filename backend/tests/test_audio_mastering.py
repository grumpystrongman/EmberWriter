"""Real FFmpeg audio loudness and normalized M4B integration.

All synthesized sources are synthetic waves, not user manuscripts.
"""
import asyncio
import gc
import math
import shutil
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

from app import storage, audiobook_jobs, audiobook_local
from app.audio_mastering import _numbers, analyze_file, report
from app.proof_approval import approve
from app.audiobook_m4b import export_m4b
from app.binder import sync_binder


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "The real mastering integration needs local FFmpeg and FFprobe")
class AudioMasteringTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.scope = patch.object(storage, "PROJECTS_ROOT", Path(self.tmp.name) / "projects")
        self.scope.start()
        self.slug = storage.create_project("Synthetic Mastering Engineering")["slug"]
        self.other = storage.create_project("Synthetic No Audio")["slug"]
        self.source = "manuscript/chapter-001.md"
        storage.save_text(self.slug, self.source, "# Listening Test\n\n" +
                          "The fictional navigator crossed the open sea. " * 40)
        sync_binder(self.slug)

    async def asyncTearDown(self):
        await audiobook_jobs.stop_on_shutdown()
        self.scope.stop()
        gc.collect()
        self.tmp.cleanup()

    @staticmethod
    def fake_sapi(command, **kwargs):
        if "-OutputPath" not in command:
            return None
        path = Path(command[command.index("-OutputPath") + 1])
        # Audible artificial tone at a well-defined amplitude, roughly -17 dBFS.
        with wave.open(str(path), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16000)
            data = bytearray()
            for n in range(16000 * 3):
                amplitude = int(32767 * .18 * math.sin(2 * math.pi * 440 * n / 16000))
                data.extend(struct.pack("<h", amplitude))
            out.writeframes(data)

    async def _narrate(self):
        with patch("app.audiobook_local.subprocess.run", side_effect=self.fake_sapi), patch(
            "app.audiobook_local.shutil.which", return_value=None
        ):
            audiobook_jobs.start(self.slug)
            for _ in range(300):
                state = audiobook_jobs.status(self.slug)
                if state["status"] in ("completed", "needs_attention") and not state["active"]:
                    self.assertEqual(state["status"], "completed", state["message"])
                    return
                await asyncio.sleep(.015)
            self.fail("Synthetic narration took too long")

    async def test_measured_tracks_and_opt_in_leveled_m4b(self):
        await self._narrate()
        approve(self.slug, self.source, 3.0, True, True)
        original = audiobook_local.audio_file(self.slug, audiobook_local.list_renders(self.slug)[0]["filename"])
        first = analyze_file(original)
        self.assertTrue(first["measured"], first)
        self.assertIsNotNone(first["integrated_lufs"])
        self.assertIsNotNone(first["true_peak_dbtp"])
        self.assertIsNotNone(first["rms_dbfs"])
        self.assertGreater(first["rms_dbfs"], -40)
        self.assertEqual(first["quiet_intervals"], 0)
        response = report(self.slug)
        self.assertEqual(len(response["tracks"]), 1)
        api = TestClient(app).post(f"/api/projects/{self.slug}/audiobook-jobs/mastering")
        self.assertEqual(api.status_code, 200, api.text)
        self.assertEqual(api.json()["tracks"][0]["path"], self.source)
        self.assertEqual(response["status"], "measured")
        self.assertEqual(response["tracks"][0]["filename"], original.name)
        # Second scan should use the persistent provenance-bound report cache.
        with patch("app.audio_mastering.analyze_file", side_effect=AssertionError("Cache miss")):
            self.assertEqual(len(report(self.slug)["tracks"]), 1)
        original_m4b = export_m4b(self.slug)
        old_bytes = original_m4b.read_bytes()
        new_m4b = export_m4b(self.slug, level=True)
        self.assertNotEqual(new_m4b, original_m4b)
        self.assertGreater(new_m4b.stat().st_size, 1024)
        self.assertEqual(original_m4b.read_bytes(), old_bytes)
        leveled = analyze_file(new_m4b)
        self.assertLessEqual(abs(leveled["integrated_lufs"] - (-18.0)), 2.5)
        self.assertLessEqual(leveled["true_peak_dbtp"], -1.0)

        storage.save_text(self.slug, self.source,
                          "# Revised\n\n" + "New source revision for synthetic story. " * 40)
        with self.assertRaisesRegex(ValueError, "verify|readiness|changed"):
            report(self.slug)
        with self.assertRaisesRegex(ValueError, "readiness"):
            export_m4b(self.slug, level=True)
        self.assertTrue(new_m4b.is_file())

    async def test_identical_source_but_replaced_audio_changes_encode_identity(self):
        from app.m4b_jobs import _identity
        await self._narrate()
        entry = audiobook_local.list_renders(self.slug)[0]
        source = audiobook_local.audio_file(self.slug, entry["filename"])
        first = _identity(self.slug)
        # A trailing byte does not change the original WAV's listed frames,
        # but it does change the physical audio artifact being exported.
        with source.open("ab") as stream:
            stream.write(b"replaced synthetic audio bytes")
        self.assertNotEqual(first, _identity(self.slug))

    def test_silence_intervals_are_not_mislabeled_ambient_noise_floor(self):
        file = Path(self.tmp.name) / "artificial-pause.wav"
        with wave.open(str(file), "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes(b"\x00\x00" * 32000)
            wav.writeframes(b"".join(struct.pack("<h", int(10000 * math.sin(2 * math.pi * 440 * n / 16000))) for n in range(16000)))
        measured = analyze_file(file)
        self.assertIsNotNone(measured["rms_dbfs"])
        self.assertGreaterEqual(measured["longest_quiet_seconds"], 1.5)
        self.assertEqual(measured["quiet_threshold_dbfs"], -50)
        self.assertNotIn("room_noise_floor", measured)
        self.assertEqual(measured["noise_floor_status"], "insufficient_quiet_samples")
        self.assertIsNone(measured["noise_floor_estimate_dbfs"])

    def test_rejects_non_numeric_ffmpeg_response(self):
        with self.assertRaisesRegex(ValueError, "loudness"):
            _numbers("garbage, not JSON")


if __name__ == "__main__":
    unittest.main()
