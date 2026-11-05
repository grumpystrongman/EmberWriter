"""Persistent local audiobook batch pipeline with synthetic SAPI rendering."""
from __future__ import annotations

import asyncio
import gc
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage
from app import audiobook_jobs
from app.binder import sync_binder
from app.main import app


class AudiobookJobTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        self.fixture.start()
        self.slug = storage.create_project("Synthetic Lantern Audiobook")["slug"]
        self.other = storage.create_project("Private Fictional Book")["slug"]
        storage.save_text(self.other, "manuscript/private.md", "NO_COPY_THIS_SECRET")
        self.chapter1 = "manuscript/chapter-001.md"
        self.chapter2 = "manuscript/chapter-002.md"
        storage.save_text(self.slug, self.chapter1,
                          "# The Beacon\n\nThe crew discovered the missing beacon. " * 15)
        storage.save_text(self.slug, self.chapter2,
                          "# The Return\n\nThe captain returned with the city lantern. " * 15)
        sync_binder(self.slug)

    async def asyncTearDown(self):
        await audiobook_jobs.stop_on_shutdown()
        self.fixture.stop()
        gc.collect()
        self.temp.cleanup()

    async def wait_for(self, goals=("completed", "paused", "needs_attention")):
        for _ in range(400):
            state = audiobook_jobs.status(self.slug)
            if state["status"] in goals and not state["active"]:
                return state
            await asyncio.sleep(.012)
        self.fail("Narration batch did not finish")

    def fake_sapi(self, cmd, **kwargs):
        if "-OutputPath" in cmd:
            target = Path(cmd[cmd.index("-OutputPath") + 1])
            with wave.open(str(target), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\x00\x00" * 16000)
        return None

    async def test_entire_book_follows_binder_and_packages_only_batch_tracks(self):
        from app.publishing import compiled_documents
        selected = compiled_documents(self.slug)
        self.assertEqual(len(selected), 2)
        with patch("app.audiobook_local.subprocess.run", side_effect=self.fake_sapi), patch(
            "app.audiobook_local.shutil.which", return_value=None
        ):
            queued = audiobook_jobs.start(self.slug)
            self.assertIn(queued["status"], ("queued", "running"))
            complete = await self.wait_for()
        self.assertEqual(complete["status"], "completed")
        self.assertEqual(complete["completed"], 2)
        self.assertEqual([ch["path"] for ch in complete["chapters"]], [doc["path"] for doc in selected])
        from app.proof_approval import approve
        for path in (self.chapter1, self.chapter2):
            approve(self.slug, path, 1.0, True, True)
        archive = audiobook_jobs.batch_archive(self.slug)
        import zipfile
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(z.namelist(), ["001-chapter.wav", "002-chapter.wav", "manifest.json"])
            manifest = z.read("manifest.json").decode("utf-8")
            self.assertNotIn("NO_COPY_THIS_SECRET", manifest)
            self.assertEqual(len(json.loads(manifest)["chapters"]), 2)
        self.assertEqual(audiobook_jobs.status(self.other)["status"], "idle")

    async def test_pause_resume_and_source_change_stops_for_attention(self):
        started = asyncio.Event()
        release = asyncio.Event()
        count = 0

        def fake_render(slug, source, voice):
            nonlocal count
            count += 1
            if count == 1:
                loop.call_soon_threadsafe(started.set)
                import time
                while not release.is_set():
                    time.sleep(.008)
            return {"filename": f"{count:016x}.wav"}

        loop = asyncio.get_running_loop()
        with patch("app.audiobook_jobs.render", side_effect=fake_render):
            audiobook_jobs.start(self.slug)
            await asyncio.wait_for(started.wait(), timeout=2)
            paused = audiobook_jobs.pause(self.slug)
            self.assertEqual(paused["status"], "paused")
            release.set()
            done = await self.wait_for(goals=("paused",))
            self.assertEqual(done["completed"], 1)
            self.assertEqual(count, 1)
            storage.save_text(self.slug, self.chapter2,
                              "# Changed story\n\n" + "The lantern suddenly faded. " * 30)
            audiobook_jobs.resume(self.slug)
            failed = await self.wait_for(goals=("needs_attention",))
            self.assertIn("changed", failed["message"])
            self.assertEqual(count, 1)

    async def test_recovery_respects_paused_jobs(self):
        from app.publishing import compiled_documents
        selected = compiled_documents(self.slug)
        record = {
            "id": "synthetic-audio-job", "status": "paused", "voice": "",
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
            "chapters": [
                {"path": x["path"], "title": x["title"],
                 "fingerprint": audiobook_jobs._fingerprint(self.slug, x["path"]),
                 "status": "queued", "filename": "", "words": len(x["content"].split())}
                for x in selected
            ],
            "current": None, "message": "paused intentionally",
        }
        audiobook_jobs._write(self.slug, record)
        with patch("app.audiobook_jobs.render") as narration:
            await audiobook_jobs.recover_on_startup()
            await asyncio.sleep(.025)
            self.assertEqual(audiobook_jobs.status(self.slug)["status"], "paused")
            narration.assert_not_called()
            record["status"] = "running"
            audiobook_jobs._write(self.slug, record)
            with patch("app.audiobook_jobs.render", return_value={"filename": "0000000000000001.wav"}):
                await audiobook_jobs.recover_on_startup()
                done = await self.wait_for(goals=("completed",))
                self.assertEqual(done["completed"], 2)

    async def test_empty_starter_and_other_projects_blocked(self):
        untouched = storage.create_project("Unused Narration Starter")["slug"]
        with self.assertRaisesRegex(ValueError, "welcome chapter"):
            audiobook_jobs.start(untouched)
        self.assertFalse(audiobook_jobs.status(untouched)["exists"])


class AudiobookJobApi(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(gc.collect)
        fixture = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        fixture.start()
        self.addCleanup(fixture.stop)
        self.slug = storage.create_project("Synthetic API Narration")["slug"]

    def test_missing_and_starter_rejected(self):
        client = TestClient(app)
        base = f"/api/projects/{self.slug}/audiobook-jobs"
        self.assertEqual(client.get(base).json()["status"], "idle")
        self.assertEqual(client.get("/api/projects/missing/audiobook-jobs").status_code, 404)
        self.assertEqual(client.post(base + "/start", json={"voice": ""}).status_code, 409)
        self.assertEqual(client.post(base + "/pause").status_code, 409)
        self.assertEqual(client.get(base + "/export").status_code, 409)


if __name__ == "__main__":
    unittest.main()
