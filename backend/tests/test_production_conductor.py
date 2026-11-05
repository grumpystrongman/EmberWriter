"""Durable author-led conductor integration; only synthetic chapters."""
import asyncio
import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import book_jobs, production_conductor, storage
from app.book_studio import approve, configure, load_state
from app.main import app
from app.models import ProviderConfig


def reader_payload():
    return json.dumps({
        "verdict": "This episode begins with a clear action.",
        "strengths": ["An evocative journey"],
        "scores": {"engagement": 4, "clarity": 4, "pacing": 3, "character": 4, "voice": 4},
        "findings": [{"category": "pacing", "quote": "Mira turned the vessel toward the shore.",
                      "issue": "The action feels abrupt.", "suggestion": "Give her decision a concrete consequence."}],
    })


class ProductionConductorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        self.fixture.start()
        self.slug = storage.create_project("Synthetic Ship Novel")["slug"]
        other = storage.create_project("Other Confidential Fiction")["slug"]
        storage.save_text(other, "manuscript/secret.md", "DO_NOT_READ_OTHER_PROJECT_TEXT")
        configure(self.slug, premise="A vessel follows the forbidden beacon.",
                  voice="Patient third-person prose", target_words=300,
                  chapters=[
                      {"title": "Arrival", "brief": "The captain approaches the forbidden beacon."},
                      {"title": "Return", "brief": "The captain comes home with a decision."},
                  ])
        self.provider = ProviderConfig(provider="ollama",
                                       base_url="http://127.0.0.1:11434", model="synthetic-local")

    async def asyncTearDown(self):
        await production_conductor.stop_on_shutdown()
        await book_jobs.stop_on_shutdown()
        self.fixture.stop()
        gc.collect()
        self.temp.cleanup()

    async def wait_for(self, target):
        for _ in range(700):
            result = production_conductor.status(self.slug)
            if result["status"] in target and not result["active"]:
                return result
            await asyncio.sleep(.015)
        self.fail("Production conductor did not reach " + str(target))

    async def test_full_pipeline_with_explicit_author_gate(self):
        writing = ("Mira turned the vessel toward the shore. "
                   "The cold stars shone above her quiet crew. " * 40)
        with patch("app.book_studio.generate_complete_prose", new_callable=AsyncMock,
                   return_value=writing) as drafted, patch(
                   "app.book_reviews.generate", new_callable=AsyncMock,
                   return_value=reader_payload()) as reviewed, patch.object(
                   production_conductor, "POLL_SECONDS", .005):
            initial = production_conductor.start(self.slug, self.provider, ["developmental_editor"])
            self.assertEqual(initial["status"], "queued")
            stopped = await self.wait_for(("awaiting_author", "needs_attention"))
        self.assertEqual(stopped["status"], "awaiting_author", stopped["message"])
        self.assertEqual(stopped["drafted"], 2)
        self.assertEqual(stopped["approved"], 0)
        self.assertEqual(drafted.call_count, 2)
        self.assertEqual(reviewed.call_count, 2)
        self.assertEqual(len([x for x in stopped["reviews_done"]]), 2)
        self.assertNotIn("DO_NOT_READ_OTHER_PROJECT_TEXT", str(reviewed.call_args_list))
        self.assertNotIn("DO_NOT_READ_OTHER_PROJECT_TEXT", str(stopped))
        self.assertEqual(load_state(self.slug)["chapters"][0]["status"], "candidate")
        approve(self.slug, 1)
        half = production_conductor.resume(self.slug)
        self.assertEqual(half["status"], "queued")
        with patch.object(production_conductor, "POLL_SECONDS", .005):
            again = await self.wait_for(("awaiting_author", "needs_attention"))
        self.assertEqual(again["status"], "awaiting_author")
        self.assertEqual(again["approved"], 1)
        approve(self.slug, 2)
        production_conductor.resume(self.slug)
        completed = await self.wait_for(("completed", "needs_attention"))
        self.assertEqual(completed["status"], "completed", completed["message"])
        self.assertTrue(completed["editorial_scan_id"])
        self.assertIsNotNone(completed["preflight"])
        self.assertEqual(completed["approved"], 2)
        self.assertEqual(completed["phase"], "publishing_handoff")
        self.assertTrue(completed["handoff_current"])
        storage.save_text(self.slug, "manuscript/book-studio/chapter-001.md",
                          "# Altered by author\n\nThe new ending changes the entire book.")
        self.assertFalse(production_conductor.status(self.slug)["handoff_current"])
        self.assertGreater(len(completed["events"]), 4)
        self.assertLessEqual(len(completed["events"]), 120)
        self.assertNotIn("The cold stars shone", str(completed["events"]))

    async def test_optional_readers_and_restart_recovery(self):
        from app.book_studio import draft_next
        writing = ("Mira turned the vessel toward the shore. "
                   "Distant lanterns illuminated a deserted bridge. " * 40)
        with patch("app.book_studio.generate_complete_prose", new_callable=AsyncMock, return_value=writing):
            await draft_next(self.slug, self.provider)
            await draft_next(self.slug, self.provider)
        initial = production_conductor.start(self.slug, self.provider, [])
        self.assertEqual(initial["personas"], [])
        final = await self.wait_for(("awaiting_author",))
        self.assertEqual(final["drafted"], 2)
        self.assertEqual(final["reviews_done"], {})
        state = production_conductor._load(self.slug)
        state["status"] = "running"
        production_conductor._write(self.slug, state)
        await production_conductor.recover_on_startup()
        recovered = await self.wait_for(("awaiting_author",))
        self.assertEqual(recovered["id"], initial["id"])

    async def test_pause_then_resume_preserves_unapproved_candidates(self):
        started = asyncio.Event()
        release = asyncio.Event()
        counter = 0

        async def synthetic_generation(*args, **kwargs):
            nonlocal counter
            counter += 1
            if counter == 1:
                started.set()
                await release.wait()
            return ("Mira turned the vessel toward the shore. "
                    "The sailors watched the first winter lantern. " * 42)

        with patch("app.book_studio.generate_complete_prose", side_effect=synthetic_generation), patch.object(
                production_conductor, "POLL_SECONDS", .005):
            production_conductor.start(self.slug, self.provider, [])
            await asyncio.wait_for(started.wait(), timeout=2)
            suspended = production_conductor.pause(self.slug)
            self.assertEqual(suspended["status"], "paused")
            release.set()
            for _ in range(150):
                if not production_conductor._running(self.slug) and not book_jobs._running(self.slug):
                    break
                await asyncio.sleep(.02)
            self.assertEqual(production_conductor.status(self.slug)["status"], "paused")
            self.assertEqual(load_state(self.slug)["chapters"][0]["status"], "candidate")
            self.assertEqual(load_state(self.slug)["chapters"][1]["status"], "planned")
            production_conductor.resume(self.slug)
            paused_then_done = await self.wait_for(("awaiting_author", "needs_attention"))
        self.assertEqual(paused_then_done["status"], "awaiting_author", paused_then_done["message"])
        self.assertEqual(paused_then_done["drafted"], 2)
        self.assertEqual(paused_then_done["approved"], 0)

    async def test_failed_reader_checkpoints_without_approving(self):
        from app.book_studio import draft_next
        writing = ("Mira turned the vessel toward the shore. "
                   "The quiet captain watched the northern light. " * 42)
        with patch("app.book_studio.generate_complete_prose", new_callable=AsyncMock, return_value=writing):
            await draft_next(self.slug, self.provider)
            await draft_next(self.slug, self.provider)
        with patch("app.book_reviews.generate", new_callable=AsyncMock,
                   side_effect=RuntimeError("synthetic Ollama unavailable")):
            production_conductor.start(self.slug, self.provider, ["genre_fan"])
            halted = await self.wait_for(("needs_attention",))
        self.assertIn("Ollama unavailable", halted["message"])
        self.assertEqual(halted["approved"], 0)
        self.assertEqual(len(halted["reviews_done"]), 0)
        with patch("app.book_reviews.generate", new_callable=AsyncMock, return_value=reader_payload()):
            production_conductor.resume(self.slug)
            final = await self.wait_for(("awaiting_author", "needs_attention"))
        self.assertEqual(final["status"], "awaiting_author")
        self.assertEqual(len(final["reviews_done"]), 2)

    async def test_reader_personas_require_explicit_opt_in(self):
        from app.routes_production_conductor import ProductionStart
        payload = ProductionStart.model_validate({"provider": self.provider.model_dump()})
        self.assertEqual(payload.personas, [])

    async def test_api_validation_and_private_scope(self):
        client = TestClient(app)
        root = f"/api/projects/{self.slug}/production-conductor"
        self.assertEqual(client.get(root).json()["status"], "idle")
        context = client.get(root + "/context/1")
        self.assertEqual(context.status_code, 200, context.text)
        self.assertLessEqual(context.json()["characters"], context.json()["budget"])
        self.assertIn("currently reconstructed", context.json()["disclaimer"])
        self.assertEqual(client.get(root + "/context/999").status_code, 404)
        self.assertEqual(client.get("/api/projects/nonexistent/production-conductor").status_code, 404)
        rejected = client.post(root + "/start", json={
            "provider": self.provider.model_dump(), "personas": ["unknown_reader"]
        })
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(client.post(root + "/pause").status_code, 409)
        self.assertEqual(client.post(root + "/continue").status_code, 409)
        forbidden = client.post(root + "/start", json={
            "provider": {"provider": "openai_compatible", "model": "synthetic",
                         "base_url": "https://remote.example"},
            "personas": [],
        })
        self.assertEqual(forbidden.status_code, 409)
        cloud_alias = client.post(root + "/start", json={
            "provider": {"provider": "ollama", "model": "demo:cloud",
                         "base_url": "http://127.0.0.1:11434"},
            "personas": [],
        })
        self.assertEqual(cloud_alias.status_code, 409)
        self.assertFalse(production_conductor.status(self.slug)["exists"])


if __name__ == "__main__":
    unittest.main()
