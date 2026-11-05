"""Evidence-backed story arc analyzer; synthetic stories only."""
import asyncio
import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.manuscript_intelligence import list_promises
from app.models import ProviderConfig
from app.story_arc_investigator import act, chapters, dossier, dossier_markdown, inspect, overview


class StoryArcInvestigatorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.addCleanup(gc.collect)
        patcher = patch.object(storage, "PROJECTS_ROOT", Path(temp.name) / "projects")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.slug = storage.create_project("Synthetic Arc Observatory")["slug"]
        other = storage.create_project("Private Other Synthetic Project")["slug"]
        storage.save_text(other, "manuscript/secret.md", "OTHER_PROJECT_SENSITIVE_STRING")
        self.chapter = "manuscript/01-beacon.md"
        self.prose = (
            "# The Beacon\n\n"
            "Mira turned the ship toward the red moon. "
            "Tavi offered to keep the signal alive. "
            "Together, they opened the lantern chamber. "
            "A hidden star map appeared.\n\n"
            "Mira lowered her sword and trusted Tavi. "
            "The promise to return before dawn remained unanswered. "
            "The ship creaked under the growing storm.\n"
        )
        storage.save_text(self.slug, self.chapter, self.prose)
        self.model = ProviderConfig(provider="ollama", base_url="http://127.0.0.1:11434",
                                    model="synthetic-offline-model")

    def _response(self):
        return json.dumps({
            "summary": "The crew discovers a map and chooses trust.",
            "tension": 4,
            "events": [
                {"kind": "choice", "label": "Mira commits to the moon",
                 "subject": "Mira", "quote": "Mira turned the ship toward the red moon.",
                 "meaning": "An active decision redirects the crew."},
                {"kind": "foreshadowing", "label": "Promise before dawn",
                 "subject": "unanswered promise",
                 "quote": "The promise to return before dawn remained unanswered.",
                 "meaning": "Might set up a future consequence."},
                {"kind": "consequence", "label": "Invented event",
                 "subject": "Tavi", "quote": "The planet exploded in a sea of golden fire.",
                 "meaning": "Fabricated evidence that must be rejected."},
            ],
        })

    def test_structured_evidence_and_author_promise_promotion(self):
        with patch("app.story_arc_investigator.generate", new_callable=AsyncMock, return_value=self._response()) as gen:
            result = asyncio.run(inspect(self.slug, self.chapter, self.model))
        self.assertEqual(len(result["events"]), 2)
        self.assertEqual(result["unverified_events_rejected"], 1)
        self.assertEqual(result["tension"], 4)
        self.assertNotIn("OTHER_PROJECT_SENSITIVE_STRING", str(gen.call_args))
        self.assertNotIn("OTHER_PROJECT_SENSITIVE_STRING", str(result))
        self.assertEqual(overview(self.slug)["analyzed"], 1)
        self.assertEqual(overview(self.slug)["review_required"], 2)
        marked = act(self.slug, result["id"], result["events"][0]["id"], "accept")
        self.assertEqual(marked["decision"], "accepted")
        self.assertEqual(len(list_promises(self.slug)), 0)
        thread = act(self.slug, result["id"], result["events"][1]["id"], "track_promise")
        self.assertEqual(thread["decision"], "accepted")
        self.assertEqual(len(list_promises(self.slug)), 1)
        self.assertEqual(list_promises(self.slug)[0]["status"], "open")
        with self.assertRaisesRegex(ValueError, "already"):
            act(self.slug, result["id"], result["events"][1]["id"], "track_promise")
        report = dossier(self.slug)
        self.assertEqual(report["analyzed"], 1)
        self.assertEqual(report["trajectories"][0]["subject"], "Mira")
        self.assertEqual(report["trajectories"][0]["events"][0]["chapter"], 1)
        markdown = dossier_markdown(self.slug)
        self.assertIn("Mira commits to the moon", markdown)
        self.assertNotIn("Invented event", markdown)
        self.assertEqual(storage.read_text(self.slug, self.chapter), self.prose)

    def test_old_analysis_rejected_after_author_edits(self):
        with patch("app.story_arc_investigator.generate", new_callable=AsyncMock, return_value=self._response()):
            result = asyncio.run(inspect(self.slug, self.chapter, self.model))
        storage.save_text(self.slug, self.chapter, self.prose + "\nThe author rewrote the final beat.")
        self.assertEqual(overview(self.slug)["analyzed"], 0)
        self.assertEqual(dossier(self.slug)["trajectories"], [])
        self.assertTrue(overview(self.slug)["historical_analyses"][0]["stale"])
        with self.assertRaisesRegex(ValueError, "older draft"):
            act(self.slug, result["id"], result["events"][0]["id"], "accept")

    def test_concurrent_author_edit_discards_analysis(self):
        async def edited(*args, **kwargs):
            storage.save_text(self.slug, self.chapter, self.prose + "\nA different ending.")
            return self._response()
        with patch("app.story_arc_investigator.generate", side_effect=edited):
            with self.assertRaisesRegex(ValueError, "edited"):
                asyncio.run(inspect(self.slug, self.chapter, self.model))
        self.assertEqual(overview(self.slug)["analyzed"], 0)

    def test_no_external_models_or_other_project_paths(self):
        self.assertEqual(len(chapters(self.slug)), 1)
        for invalid in (
            ProviderConfig(provider="openai_compatible", base_url="https://offsite.example", model="cloud"),
            ProviderConfig(provider="ollama", base_url="http://127.0.0.1:11434", model="gemma4:31b-cloud"),
        ):
            with patch("app.story_arc_investigator.generate", new_callable=AsyncMock) as gen:
                with self.assertRaises(ValueError):
                    asyncio.run(inspect(self.slug, self.chapter, invalid))
                gen.assert_not_called()
        with self.assertRaises(FileNotFoundError):
            asyncio.run(inspect(self.slug, "../other/secret.md", self.model))

    def test_invalid_model_schema_does_not_persist(self):
        with patch("app.story_arc_investigator.generate", new_callable=AsyncMock,
                   return_value='{"summary":"fine","tension":9,"events":[]}'):
            with self.assertRaisesRegex(ValueError, "incomplete"):
                asyncio.run(inspect(self.slug, self.chapter, self.model))
        self.assertEqual(overview(self.slug)["analyzed"], 0)

    def test_api_is_project_scoped_and_no_automatic_manuscript_writes(self):
        client = TestClient(app)
        root = f"/api/projects/{self.slug}/story-arcs"
        self.assertEqual(client.get(root).json()["analyzed"], 0)
        self.assertEqual(client.get(root + "/dossier").status_code, 200)
        self.assertEqual(client.get(root + "/dossier.md").status_code, 200)
        self.assertEqual(client.get("/api/projects/not-a-real-project/story-arcs").status_code, 404)
        response = client.post(root + "/inspect", json={
            "path": self.chapter, "provider": {
                "provider": "ollama", "model": "gemma4:31b-cloud",
                "base_url": "http://127.0.0.1:11434",
            },
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(storage.read_text(self.slug, self.chapter), self.prose)


if __name__ == "__main__":
    unittest.main()
