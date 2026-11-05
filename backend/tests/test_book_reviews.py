"""Evidence-bound, author-controlled reader panel; synthetic projects only."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import storage
from app.book_reviews import brief, decide, evaluate, history
from app.book_studio import candidate, configure, draft_next, edit_candidate
from app.main import app
from app.models import ProviderConfig


class BookReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.slug = storage.create_project("Synthetic Review Novel")["slug"]
        other = storage.create_project("Another Fictional Project")["slug"]
        storage.save_text(other, "world/secret.md", "DO_NOT_INCLUDE_OTHER_PROJECT")
        self.model = ProviderConfig(provider="ollama", base_url="http://127.0.0.1:11434",
                                    model="synthetic-model")
        configure(self.slug, premise="A crew navigates lantern signals", voice="hopeful",
                  chapters=[{"title": "The Signal", "brief": "Find a beacon"}], target_words=300)
        self.prose = ("The navigator studied the signal. "
                      "The captain steadied the ship. " * 36)
        with patch("app.book_studio.generate_complete_prose", new_callable=AsyncMock, return_value=self.prose):
            asyncio.run(draft_next(self.slug, self.model))

    def response(self):
        return json.dumps({
            "verdict": "A promising beginning with a clear goal.",
            "strengths": ["The captain has agency."],
            "scores": {"engagement": 4, "clarity": 5, "pacing": 3, "character": 4, "voice": 4},
            "findings": [
                {"category": "pacing", "quote": "The navigator studied the signal.",
                 "issue": "The action repeats too often.", "suggestion": "Vary the sequence."},
                {"category": "style", "quote": "This sentence was invented by the reviewer.",
                 "issue": "Hallucinated critique.", "suggestion": "Replace it."},
            ],
        })

    def test_verified_quotes_and_author_approval(self):
        with patch("app.book_reviews.generate", new_callable=AsyncMock, return_value=self.response()):
            review = asyncio.run(evaluate(self.slug, 1, "developmental_editor", self.model))
        self.assertEqual(len(review["findings"]), 1)
        self.assertEqual(review["unverified_findings_rejected"], 1)
        self.assertEqual(review["findings"][0]["decision"], "pending")
        self.assertEqual(brief(self.slug, 1)["count"], 0)
        self.assertEqual(history(self.slug, 1)["reviews"][0]["persona"], "developmental_editor")
        finding = review["findings"][0]
        before = candidate(self.slug, 1)["content"]
        decision = decide(self.slug, 1, review["id"], finding["id"], "accept")
        self.assertEqual(decision["decision"], "accepted")
        self.assertEqual(brief(self.slug, 1)["count"], 1)
        self.assertEqual(candidate(self.slug, 1)["content"], before)
        self.assertNotIn("DO_NOT_INCLUDE_OTHER_PROJECT", str(review))

    def test_changed_candidate_invalidates_prior_verdict(self):
        with patch("app.book_reviews.generate", new_callable=AsyncMock, return_value=self.response()):
            review = asyncio.run(evaluate(self.slug, 1, "genre_fan", self.model))
        edit_candidate(self.slug, 1, candidate(self.slug, 1)["content"] + "\nAn additional author-written ending.")
        self.assertTrue(history(self.slug, 1)["reviews"][0]["stale"])
        with self.assertRaisesRegex(ValueError, "older draft"):
            decide(self.slug, 1, review["id"], "f0", "accept")
        self.assertEqual(brief(self.slug, 1)["count"], 0)

    def test_external_and_cloud_alias_models_rejected(self):
        models = (
            ProviderConfig(provider="openai_compatible", base_url="https://example.com", model="offsite"),
            ProviderConfig(provider="ollama", base_url="http://127.0.0.1:11434", model="gemma4:31b-cloud"),
        )
        for model in models:
            with patch("app.book_reviews.generate", new_callable=AsyncMock) as mock:
                with self.assertRaises(ValueError):
                    asyncio.run(evaluate(self.slug, 1, "line_editor", model))
                mock.assert_not_called()

    def test_routes_and_project_isolation(self):
        client = TestClient(app)
        base = f"/api/projects/{self.slug}/book-reviews"
        response = client.get(base + "/personas")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 3)
        self.assertEqual(client.get(base + "/1").json()["reviews"], [])
        self.assertEqual(client.get("/api/projects/unknown/book-reviews/1").status_code, 404)
        remote = client.post(base + "/1/evaluate", json={
            "persona": "line_editor", "provider": {
                "provider": "ollama", "base_url": "http://127.0.0.1:11434",
                "model": "gemma4:31b-cloud",
            }})
        self.assertEqual(remote.status_code, 400)

    def test_malformed_model_response_never_saved(self):
        invalid = '{"verdict":"x", "scores":{"engagement":99}, "findings":[]}'
        with patch("app.book_reviews.generate", new_callable=AsyncMock, return_value=invalid):
            with self.assertRaises(ValueError):
                asyncio.run(evaluate(self.slug, 1, "line_editor", self.model))
        self.assertEqual(history(self.slug, 1)["reviews"], [])


if __name__ == "__main__":
    unittest.main()
