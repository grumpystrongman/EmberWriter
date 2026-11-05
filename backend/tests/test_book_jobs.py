"""Durable book drafting tests with synthetic data, never user manuscripts."""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import book_jobs, storage
from app.book_studio import configure, load_state
from app.main import app
from app.models import ProviderConfig


class BackgroundBookJobs(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patcher = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        self.patcher.start()
        self.slug = storage.create_project("Fictional Lantern Journey")["slug"]
        self.other = storage.create_project("Hidden Second Project")["slug"]
        storage.save_text(self.other, "world/secret.md", "SYNTHETIC_PRIVATE_OTHER_PROJECT")
        self.model = ProviderConfig(provider="ollama", model="synthetic-local-model",
                                    base_url="http://127.0.0.1:11434")
        configure(self.slug, premise="A captain repairs a city's lanterns", voice="Science fantasy",
                  target_words=300, chapters=[
                      {"title": "Arrival", "brief": "A lantern fades"},
                      {"title": "Mystery", "brief": "A map gives new direction"},
                      {"title": "Resolution", "brief": "Save the city with shared courage"},
                  ])
        self.sample = ("The lantern glowed when the captain turned toward the distant mountains. " * 30).strip()

    async def asyncTearDown(self):
        await book_jobs.stop_on_shutdown()
        self.patcher.stop()
        self.temp.cleanup()

    async def wait_for(self, terminal=("completed", "paused", "needs_attention"), seconds=3):
        for _ in range(int(seconds * 100)):
            result = book_jobs.status(self.slug)
            if result["status"] in terminal and not result["active"]:
                return result
            await asyncio.sleep(.01)
        self.fail("Book job did not reach terminal state")

    async def test_whole_book_run_survives_closed_browser_and_never_approves(self):
        async def generated(*args, **kwargs):
            self.assertNotIn("SYNTHETIC_PRIVATE_OTHER_PROJECT", str(args))
            return self.sample
        with patch("app.book_studio.generate_complete_prose", side_effect=generated):
            model_with_unused_secret = self.model.model_copy(update={"api_key": "NEVER_PERSIST_THIS_SECRET"})
            queued = book_jobs.start(self.slug, model_with_unused_secret)
            self.assertIn(queued["status"], ("queued", "running"))
            self.assertNotIn("NEVER_PERSIST_THIS_SECRET", book_jobs._path(self.slug).read_text(encoding="utf-8"))
            done = await self.wait_for()
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["drafted"], 3)
        self.assertEqual(done["approved"], 0)
        self.assertEqual(done["completed_in_run"], 3)
        self.assertTrue(all(ch["status"] == "candidate" for ch in load_state(self.slug)["chapters"]))
        self.assertFalse((storage.project_root(self.slug) / "manuscript/book-studio/chapter-001.md").exists())
        self.assertEqual(book_jobs.status(self.other)["status"], "idle")
        serialized = json.dumps(book_jobs.status(self.slug))
        self.assertNotIn("SYNTHETIC_PRIVATE_OTHER_PROJECT", serialized)
        self.assertNotIn("provider", book_jobs.status(self.slug))

    async def test_pause_finishes_chapter_then_resume(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def generated(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                entered.set()
                await release.wait()
            return self.sample

        with patch("app.book_studio.generate_complete_prose", side_effect=generated):
            book_jobs.start(self.slug, self.model)
            await asyncio.wait_for(entered.wait(), timeout=2)
            paused = book_jobs.pause(self.slug)
            self.assertEqual(paused["status"], "paused")
            self.assertEqual(book_jobs.status(self.slug)["current_chapter"], 1)
            release.set()
            done = await self.wait_for(terminal=("paused",))
            self.assertEqual(done["drafted"], 1)
            self.assertEqual(calls, 1)
            await asyncio.sleep(.02)
            self.assertEqual(calls, 1)
            self.assertEqual(book_jobs.resume(self.slug)["status"], "queued")
            complete = await self.wait_for(terminal=("completed",))
            self.assertEqual(complete["drafted"], 3)
            self.assertEqual(calls, 3)

    async def test_crash_recovery_requeues_only_authorized_jobs(self):
        job = {
            "id": "synthetic-recovery", "status": "running",
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
            "provider": self.model.model_dump(), "completed_in_run": 0,
            "current_chapter": 1, "message": "interrupted",
        }
        book_jobs._write(self.slug, job)
        with patch("app.book_studio.generate_complete_prose", return_value=self.sample):
            await book_jobs.recover_on_startup()
            self.assertIn(book_jobs.status(self.slug)["status"], ("queued", "running"))
            self.assertEqual((await self.wait_for())["status"], "completed")

        second = book_jobs._load(self.slug)
        second["status"] = "paused"
        book_jobs._write(self.slug, second)
        with patch("app.book_studio.generate_complete_prose") as generated:
            await book_jobs.recover_on_startup()
            await asyncio.sleep(.03)
            self.assertEqual(book_jobs.status(self.slug)["status"], "paused")
            generated.assert_not_called()

    async def test_shutdown_interrupts_inflight_draft_and_restart_recovers(self):
        entered = asyncio.Event()
        async def stuck(*args, **kwargs):
            entered.set()
            await asyncio.Event().wait()
        with patch("app.book_studio.generate_complete_prose", side_effect=stuck):
            book_jobs.start(self.slug, self.model)
            await asyncio.wait_for(entered.wait(), timeout=2)
            await book_jobs.stop_on_shutdown()
        self.assertEqual(book_jobs._load(self.slug)["status"], "running")
        self.assertEqual(load_state(self.slug)["chapters"][0]["status"], "failed")
        with patch("app.book_studio.generate_complete_prose", return_value=self.sample):
            await book_jobs.recover_on_startup()
            completed = await self.wait_for()
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["drafted"], 3)

    async def test_error_stops_job_without_hiding_failure(self):
        async def broken(*args, **kwargs):
            raise RuntimeError("Synthetic model deliberately offline")
        with patch("app.book_studio.generate_complete_prose", side_effect=broken):
            book_jobs.start(self.slug, self.model)
            failed = await self.wait_for(terminal=("needs_attention",))
            self.assertEqual(failed["status"], "needs_attention")
            self.assertIn("Synthetic model", failed["message"])
            self.assertEqual(load_state(self.slug)["chapters"][0]["status"], "failed")

    async def test_cloud_endpoints_rejected_before_queue(self):
        remote = ProviderConfig(provider="openai_compatible", model="remote",
                                base_url="https://remote.example/v1")
        with self.assertRaisesRegex(ValueError, "local Ollama"):
            book_jobs.start(self.slug, remote)
        hosted_alias = ProviderConfig(provider="ollama", model="gemma4:31b-cloud",
                                      base_url="http://127.0.0.1:11434")
        with self.assertRaisesRegex(ValueError, "cloud models"):
            book_jobs.start(self.slug, hosted_alias)
        self.assertEqual(book_jobs.status(self.slug)["status"], "idle")


class BookJobsApi(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.slug = storage.create_project("Synthetic Job API")["slug"]
        configure(self.slug, premise="The first lantern is missing", voice="Soft wonder",
                  target_words=300, chapters=[{"title": "One", "brief": "Find the beacon"}])

    def test_unknown_project_and_cloud_disallowed(self):
        client = TestClient(app)
        root = f"/api/projects/{self.slug}/book-jobs"
        self.assertEqual(client.get(root).json()["status"], "idle")
        self.assertEqual(client.get("/api/projects/nonexistent/book-jobs").status_code, 404)
        response = client.post(root + "/start", json={"provider": {
            "provider": "openai_compatible", "base_url": "https://remote.example",
            "model": "remote"
        }})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(client.post(root + "/pause").status_code, 409)


if __name__ == "__main__":
    unittest.main()
