"""Synthetic-only audiobook quality and pacing regression tests."""
from __future__ import annotations

import asyncio
import gc
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import audiobook_jobs, audiobook_local, storage
from app.audiobook_quality import _file_diagnostics, inspect
from app.proof_approval import approve
from app.binder import sync_binder
from app.main import app


class AudioQualityChecks(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.scope = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        self.scope.start()
        self.slug = storage.create_project("Synthetic Narration Quality")["slug"]
        self.other = storage.create_project("Synthetic Other Narration")["slug"]
        storage.save_text(self.other, "manuscript/other.md", "NEVER_INCLUDE_THE_OTHER_BOOK")
        self.source = "manuscript/chapter-001.md"
        storage.save_text(self.slug, self.source,
                          "# A Lamp Returns\n\n" + ("A kind navigator carried a quiet lantern across the valley. " * 20))
        sync_binder(self.slug)
        self.calls = []

    async def asyncTearDown(self):
        await audiobook_jobs.stop_on_shutdown()
        self.scope.stop()
        gc.collect()
        self.temp.cleanup()

    def fake_sapi(self, command, **kwargs):
        if "-OutputPath" not in command:
            return None
        self.calls.append(command)
        target = Path(command[command.index("-OutputPath") + 1])
        with wave.open(str(target), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x05\x00" * 16000)
        return None

    async def wait_done(self):
        for _ in range(300):
            result = audiobook_jobs.status(self.slug)
            if result["status"] in ("completed", "needs_attention") and not result["active"]:
                return result
            await asyncio.sleep(.012)
        self.fail("Timed out waiting for synthetic audio worker")

    async def test_rate_is_forwarded_and_provenance_is_verified(self):
        with patch("app.audiobook_local.subprocess.run", side_effect=self.fake_sapi), patch(
            "app.audiobook_local.shutil.which", return_value=None
        ):
            queued = audiobook_jobs.start(self.slug, rate=2)
            self.assertEqual(queued["rate"], 2)
            done = await self.wait_done()
        self.assertEqual(done["status"], "completed")
        self.assertIn("-Rate", self.calls[0])
        self.assertEqual(self.calls[0][self.calls[0].index("-Rate") + 1], "2")
        track = audiobook_local.list_renders(self.slug)[0]
        self.assertEqual(track["rate"], 2)
        self.assertEqual(track["source_hash"], audiobook_jobs._fingerprint(self.slug, self.source))
        self.assertFalse(inspect(self.slug)["ready"])
        approve(self.slug, self.source, 1.0, True, True)
        ready = inspect(self.slug)
        self.assertTrue(ready["ready"], ready)
        self.assertEqual(ready["verified_tracks"], 1)
        self.assertEqual(ready["duration_seconds"], 1.0)
        response = TestClient(app).get(f"/api/projects/{self.slug}/audiobook-jobs/quality")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("NEVER_INCLUDE_THE_OTHER_BOOK", response.text)
        self.assertEqual(len(inspect(self.other)["tracks"]), 0)
        self.assertIn("not_started", inspect(self.other)["status"])

        storage.save_text(self.slug, self.source,
                          "# Revised\n\n" + ("The navigator left the lantern behind. " * 20))
        stale = inspect(self.slug)
        self.assertFalse(stale["ready"])
        self.assertTrue(any("changed" in item["detail"] for item in stale["issues"]))
        with self.assertRaisesRegex(ValueError, "changed since narration"):
            audiobook_jobs.batch_archive(self.slug)

    async def test_wav_corruption_and_legacy_provenance_are_flagged(self):
        with patch("app.audiobook_local.subprocess.run", side_effect=self.fake_sapi), patch(
            "app.audiobook_local.shutil.which", return_value=None
        ):
            audiobook_jobs.start(self.slug)
            self.assertEqual((await self.wait_done())["status"], "completed")
        approve(self.slug, self.source, 1.0, True, True)
        self.assertTrue(inspect(self.slug)["ready"])
        entry = audiobook_local.list_renders(self.slug)[0]
        wav = audiobook_local.audio_file(self.slug, entry["filename"])
        wav.write_bytes(b"not really a wave")
        report = inspect(self.slug)
        self.assertFalse(report["ready"])
        self.assertIn("Unreadable WAV", str(report["issues"]))
        wav.unlink()

        manifest = audiobook_local._read_manifest(self.slug)
        manifest["chapters"][0].pop("source_hash", None)
        audiobook_local._save_manifest(self.slug, manifest)
        # A missing track and unversioned legacy render can never appear verified.
        self.assertFalse(inspect(self.slug)["ready"])

    async def test_invalid_rate_does_not_create_a_job(self):
        with self.assertRaisesRegex(ValueError, "speed"):
            audiobook_jobs.start(self.slug, rate=11)
        self.assertEqual(TestClient(app).post(
            f"/api/projects/{self.slug}/audiobook-jobs/start",
            json={"voice": "", "rate": 99},
        ).status_code, 422)
        self.assertFalse(audiobook_jobs.status(self.slug)["exists"])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                         "This integration requires locally installed FFmpeg and FFprobe")
    async def test_real_ffmpeg_builds_one_chapter_marker_without_cloud(self):
        from app.audiobook_m4b import export_m4b
        import json
        import subprocess
        with patch("app.audiobook_local.subprocess.run", side_effect=self.fake_sapi), patch(
            "app.audiobook_local.shutil.which", return_value=None
        ):
            audiobook_jobs.start(self.slug)
            self.assertEqual((await self.wait_done())["status"], "completed")
        approve(self.slug, self.source, 1.0, True, True)
        output = export_m4b(self.slug)
        self.assertTrue(output.is_file())
        self.assertGreater(output.stat().st_size, 1024)
        details = subprocess.run(
            [shutil.which("ffprobe"), "-v", "error", "-show_chapters",
             "-show_entries", "chapter=start_time,end_time:chapter_tags=title",
             "-of", "json", str(output)],
            capture_output=True, text=True, check=True, timeout=25,
        )
        chapters = json.loads(details.stdout)["chapters"]
        self.assertEqual(len(chapters), 1)
        self.assertGreater(float(chapters[0]["end_time"]), 0)
        self.assertEqual(chapters[0]["tags"]["title"], "A Lamp Returns")
        self.assertNotIn("NEVER_INCLUDE_THE_OTHER_BOOK", str(chapters))
        previous = output.read_bytes()
        storage.save_text(self.slug, self.source,
                          "# Revised Audio Source\n\n" + "The lantern has changed again. " * 30)
        with self.assertRaisesRegex(ValueError, "readiness"):
            export_m4b(self.slug)
        self.assertEqual(output.read_bytes(), previous)

    def test_wave_quality_inspection_rejects_truncated_audio(self):
        path = Path(self.temp.name) / "bad.wav"
        path.write_bytes(b"Riff invalid")
        self.assertFalse(_file_diagnostics(path)["valid"])


if __name__ == "__main__":
    unittest.main()
