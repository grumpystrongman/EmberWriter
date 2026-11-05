"""Durable M4B encoding jobs: synthetic author projects only."""
from __future__ import annotations

import asyncio
import gc
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import m4b_jobs, storage
from app.local_resources import reservation
from app.main import app


class M4BJobTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.scope = patch.object(storage, "PROJECTS_ROOT", Path(self.tmp.name) / "projects")
        self.scope.start()
        self.slug = storage.create_project("Synthetic Local M4B Jobs")["slug"]
        self.identity_scope = patch("app.m4b_jobs._identity", return_value="synthetic-batch-identity")
        self.identity_scope.start()
        self.other = storage.create_project("Synthetic Other M4B")["slug"]

    async def asyncTearDown(self):
        await m4b_jobs.stop_on_shutdown()
        self.identity_scope.stop()
        self.scope.stop()
        gc.collect()
        self.tmp.cleanup()

    async def settle(self):
        for _ in range(300):
            result = m4b_jobs.status(self.slug)
            if result["status"] in ("completed", "needs_attention", "interrupted") and not result["active"]:
                return result
            await asyncio.sleep(.012)
        self.fail("Synthetic encode did not finish")

    async def test_start_persist_complete_and_isolation(self):
        target = storage.project_root(self.slug) / ".ember" / "audiobook" / "current-book-narration.m4b"
        def fake_export(slug, *, level, cancel_event, progress):
            self.assertEqual(slug, self.slug)
            self.assertFalse(level)
            self.assertIsInstance(cancel_event, threading.Event)
            progress("encoding")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"synthetic encoded audio")
            progress("verifying")
            return target
        with patch("app.audiobook_quality.inspect", return_value={"ready":True}), patch(
            "app.audiobook_m4b.export_m4b", side_effect=fake_export
        ):
            started = m4b_jobs.start(self.slug)
            self.assertEqual(started["mode"], "original")
            done = await self.settle()
        self.assertEqual(done["status"], "completed", done)
        self.assertEqual(done["filename"], target.name)
        self.assertEqual(m4b_jobs.status(self.other)["status"], "idle")
        self.assertFalse(m4b_jobs._active(self.slug))
        with patch("app.audiobook_quality.inspect", return_value={"ready":True}):
            response = TestClient(app).get(f"/api/projects/{self.slug}/m4b-jobs/download")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, b"synthetic encoded audio")
        self.assertEqual(TestClient(app).get(f"/api/projects/{self.other}/m4b-jobs/download").status_code, 409)

    async def test_pause_queued_then_resume_leveled(self):
        target = storage.project_root(self.slug) / ".ember" / "audiobook" / "current-book-narration-leveled.m4b"
        def fake_export(slug, *, level, cancel_event, progress):
            self.assertTrue(level)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"synthetic leveled audio")
            return target
        with patch("app.audiobook_quality.inspect", return_value={"ready":True}), patch(
            "app.audiobook_m4b.export_m4b", side_effect=fake_export
        ):
            async with reservation():
                initial = m4b_jobs.start(self.slug, "leveled")
                self.assertEqual(initial["status"], "queued")
                paused = m4b_jobs.pause(self.slug)
                self.assertEqual(paused["status"], "paused")
            await asyncio.sleep(.08)
            self.assertFalse(m4b_jobs._active(self.slug))
            queued = m4b_jobs.resume(self.slug)
            self.assertEqual(queued["mode"], "leveled")
            self.assertEqual((await self.settle())["status"], "completed")

    async def test_startup_recovers_abandoned_encode(self):
        target = storage.project_root(self.slug) / ".ember" / "audiobook" / "current-book-narration.m4b"
        m4b_jobs._write(self.slug, {
            "id":"synthetic-resume-id", "mode":"original", "status":"encoding",
            "message":"Interrupted synthetic process", "filename":"", "created_at":"synthetic",
            "input_identity":"synthetic-batch-identity",
        })
        def fake_export(slug, *, level, cancel_event, progress):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"recovered synthetic media")
            return target
        with patch("app.audiobook_m4b.export_m4b", side_effect=fake_export):
            await m4b_jobs.recover_on_startup()
            result = await self.settle()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["id"], "synthetic-resume-id")

    async def test_shutdown_cancels_encoder_and_remains_recoverable(self):
        entered = threading.Event()
        terminated = threading.Event()
        def fake_export(slug, *, level, cancel_event, progress):
            entered.set()
            while not cancel_event.wait(.005):
                pass
            terminated.set()
            raise RuntimeError("synthetic interruption")
        with patch("app.audiobook_quality.inspect", return_value={"ready":True}), patch(
            "app.audiobook_m4b.export_m4b", side_effect=fake_export
        ):
            m4b_jobs.start(self.slug)
            for _ in range(100):
                if entered.is_set():
                    break
                await asyncio.sleep(.01)
            self.assertTrue(entered.is_set())
            await m4b_jobs.stop_on_shutdown()
        self.assertTrue(terminated.is_set())
        self.assertEqual(m4b_jobs.status(self.slug)["status"], "interrupted")

    async def test_cancel_active_subprocess_reaps_child(self):
        import sys

        from app.audiobook_m4b import _run_checked
        event = threading.Event()
        started = threading.Event()
        result = []
        def work():
            started.set()
            try:
                _run_checked([sys.executable, "-c", "import time; time.sleep(20)"], timeout=25, cancel_event=event)
            except RuntimeError as exc:
                result.append(str(exc))
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        await asyncio.to_thread(started.wait, 3)
        await asyncio.sleep(.15)
        event.set()
        await asyncio.to_thread(thread.join, 4)
        self.assertFalse(thread.is_alive(), "Cancellation failed to reap FFmpeg-like child")
        self.assertTrue(any("cancelled" in entry for entry in result), result)

    async def test_api_bad_mode_and_missing_project(self):
        api = TestClient(app)
        bad = api.post(f"/api/projects/{self.slug}/m4b-jobs/start", json={"mode":"cloud"})
        self.assertEqual(bad.status_code, 409)
        missing = api.get("/api/projects/does-not-exist/m4b-jobs")
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
