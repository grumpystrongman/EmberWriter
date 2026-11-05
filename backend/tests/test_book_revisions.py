"""Synthetic, non-destructive revision intelligence tests."""
from __future__ import annotations

import asyncio
import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import storage
from app.book_reviews import decide as decide_finding
from app.book_reviews import evaluate
from app.book_revisions import decide, list_proposals, propose
from app.book_studio import candidate, configure, draft_next, edit_candidate
from app.main import app
from app.models import ProviderConfig


class RevisionIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(gc.collect)
        patcher = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.slug = storage.create_project("Synthetic Lantern Story")["slug"]
        other = storage.create_project("Other Synthetic Secret Story")["slug"]
        storage.save_text(other, "world/private.md", "NEVER_READ_OTHER_PROJECT")
        self.model = ProviderConfig(provider="ollama", base_url="http://127.0.0.1:11434", model="local-dummy")
        configure(self.slug, premise="A captain discovers a signal.", voice="Close third and distinctive.",
                  target_words=300, chapters=[{"title": "Signal", "brief": "The captain must decide."}])
        self.prose = ("The navigator studied the distant lights. "
                      "The captain turned the ship north. " * 38)
        with patch("app.book_studio.generate_complete_prose", new_callable=AsyncMock, return_value=self.prose):
            asyncio.run(draft_next(self.slug, self.model))

    def _accepted_reader(self):
        quote = "The captain turned the ship north."
        response = json.dumps({
            "verdict": "The chapter has energy.",
            "strengths": ["Distinct setting"],
            "scores": {"engagement": 4, "clarity": 4, "pacing": 3, "character": 4, "voice": 4},
            "findings": [{"category": "pacing", "quote": quote,
                          "issue": "This repeats.", "suggestion": "Vary the dramatic escalation."}],
        })
        with patch("app.book_reviews.generate", new_callable=AsyncMock, return_value=response):
            review = asyncio.run(evaluate(self.slug, 1, "developmental_editor", self.model))
        decide_finding(self.slug, 1, review["id"], review["findings"][0]["id"], "accept")

    def _propose(self):
        original = candidate(self.slug, 1)["content"]
        rewritten = original.replace("The captain turned the ship north.", "The captain followed the beacon east.")
        with patch("app.book_revisions.generate", new_callable=AsyncMock, return_value=rewritten) as generated:
            result = asyncio.run(propose(self.slug, 1, self.model))
            self.assertEqual(generated.call_count, 1)
            self.assertNotIn("NEVER_READ_OTHER_PROJECT", str(generated.call_args))
        return result

    def test_proposal_is_separate_and_author_acceptance_preserves_original(self):
        self._accepted_reader()
        original = candidate(self.slug, 1)["content"]
        proposal = self._propose()
        self.assertEqual(candidate(self.slug, 1)["content"], original)
        self.assertEqual(proposal["status"], "proposed")
        self.assertGreater(proposal["metrics"]["added_lines"], 0)
        self.assertEqual(proposal["accepted_findings"], 1)
        decided = decide(self.slug, 1, proposal["id"], "accept")
        self.assertEqual(decided["status"], "accepted")
        updated = candidate(self.slug, 1)["content"]
        self.assertIn("followed the beacon east", updated)
        versions = list((storage.project_root(self.slug) / ".ember" / "book-candidate-revisions" / "chapter-001").glob("*.md"))
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].read_text(encoding="utf-8"), original)
        with self.assertRaisesRegex(ValueError, "already"):
            decide(self.slug, 1, proposal["id"], "accept")

    def test_author_rejection_preserves_candidate(self):
        original = candidate(self.slug, 1)["content"]
        revised = original.replace("The captain turned the ship north.", "The captain followed the beacon east.")
        with patch("app.book_revisions.generate", new_callable=AsyncMock, return_value=revised):
            proposal = asyncio.run(propose(self.slug, 1, self.model, "Change the direction toward the beacon."))
        self.assertEqual(decide(self.slug, 1, proposal["id"], "reject")["status"], "rejected")
        self.assertEqual(candidate(self.slug, 1)["content"], original)

    def test_stale_revision_cannot_overwrite_author_edits(self):
        self._accepted_reader()
        proposal = self._propose()
        current = candidate(self.slug, 1)["content"]
        edit_candidate(self.slug, 1, current + "\nThe author changes the ending.")
        self.assertTrue(list_proposals(self.slug, 1)["proposals"][0]["stale"])
        with self.assertRaisesRegex(ValueError, "changed"):
            decide(self.slug, 1, proposal["id"], "accept")
        self.assertIn("The author changes", candidate(self.slug, 1)["content"])

    def test_generation_discards_stale_proposal_after_await(self):
        original = candidate(self.slug, 1)["content"]
        revised = original.replace("The captain turned the ship north.", "The captain followed the beacon east.")
        async def concurrent_author_edit(*args, **kwargs):
            edit_candidate(self.slug, 1, original + "\nThe author revised meanwhile.")
            return revised
        with patch("app.book_revisions.generate", side_effect=concurrent_author_edit):
            with self.assertRaisesRegex(ValueError, "changed during"):
                asyncio.run(propose(self.slug, 1, self.model, "Vary the action."))
        self.assertEqual(list_proposals(self.slug, 1)["proposals"], [])

    def test_short_generation_rejected_and_cloud_rejected(self):
        original = candidate(self.slug, 1)["content"]
        with patch("app.book_revisions.generate", new_callable=AsyncMock, return_value="Very short."):
            with self.assertRaisesRegex(ValueError, "incomplete"):
                asyncio.run(propose(self.slug, 1, self.model, "Improve tension."))
        self.assertEqual(candidate(self.slug, 1)["content"], original)
        for model in (
            ProviderConfig(provider="openai_compatible", base_url="https://remote.example", model="x"),
            ProviderConfig(provider="ollama", base_url="http://127.0.0.1:11434", model="gemma4:31b-cloud"),
        ):
            with patch("app.book_revisions.generate", new_callable=AsyncMock) as generated:
                with self.assertRaises(ValueError):
                    asyncio.run(propose(self.slug, 1, model, "Improve tension."))
                generated.assert_not_called()

    def test_api_and_path_scope(self):
        client = TestClient(app)
        base = f"/api/projects/{self.slug}/book-revisions"
        self.assertEqual(client.get(base + "/1").json()["proposals"], [])
        self.assertEqual(client.get("/api/projects/nonexistent/book-revisions/1").status_code, 404)
        response = client.post(base + "/1/propose", json={
            "provider": {"provider": "ollama", "base_url": "http://127.0.0.1:11434", "model": "x-cloud"},
            "author_direction": "Focus on pacing.",
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(client.get(base + "/1/garbage").status_code, 404)


if __name__ == "__main__":
    unittest.main()
