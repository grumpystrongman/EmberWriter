"""Book Studio: author-directed local whole-book candidate pipeline."""
from __future__ import annotations

import asyncio
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import storage
from app.book_studio import (
    approve, candidate, configure, decline, draft_next, load_state, revise_chapter_brief, edit_candidate, suggest_outline,
)
from app.main import app
from app.models import ProviderConfig


class BookStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(gc.collect)
        patcher = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.project = storage.create_project("Synthetic Test Novel")
        self.slug = self.project["slug"]
        self.private = storage.create_project("Top Secret Other Project")
        storage.save_text(self.private["slug"], "world/secret.md", "DO_NOT_SHARE_THIS")
        storage.save_text(self.slug, "world/planet.md", "The planet has two moons.")
        self.local = ProviderConfig(provider="ollama", base_url="http://127.0.0.1:11434",
                                    model="fictional-local-model")
        self.plan = [{"title": "Arrival", "brief": "Discover a coded beacon."},
                     {"title": "Crossing", "brief": "Cross the floating islands together."}]

    def setup_plan(self):
        return configure(self.slug, premise="An engineer discovers a magical signal.", voice="Close third, hopeful",
                         chapters=self.plan, target_words=300)

    def test_plan_is_local_and_non_destructive(self):
        self.assertFalse(load_state(self.slug)["configured"])
        state = self.setup_plan()
        self.assertEqual(len(state["chapters"]), 2)
        self.assertFalse((storage.project_root(self.slug) / "manuscript/book-studio/chapter-001.md").exists())
        self.assertNotIn("DO_NOT_SHARE_THIS", str(state))
        with self.assertRaisesRegex(ValueError, "requires"):
            configure(self.slug, premise="Test", voice="", chapters=[], target_words=300)

    def test_bounded_continuity_context_uses_original_chapter_evidence(self):
        from app.book_studio import _context, MAX_CONTEXT
        from app.manuscript_intelligence import create_promise
        chapters = [{"title": f"Chapter {i}", "brief": f"Beat {i}"} for i in range(1, 13)]
        configure(self.slug, premise="A distant city is found.", voice="Close third.",
                  chapters=chapters, target_words=300)
        for index in range(1, 12):
            document = f"# Chapter {index}\n\n" + ("Opening discovery by Mara. " * 20)
            document += f"EARLIER_SOURCE_ENDING_{index} " + ("The captain rested. " * 15)
            file = storage.project_root(self.slug) / ".ember" / "book-candidates" / f"chapter-{index:03d}.md"
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(document, encoding="utf-8")
        state = load_state(self.slug)
        for chapter in state["chapters"][:11]:
            chapter["status"] = "candidate"
        create_promise(self.slug, "The sealed vault", "sealed vault",
                       "The author will decide when the vault opens.")
        storage.save_text(self.slug, "world/canon.md",
                          "The northern city is surrounded by seven rivers.")
        context = _context(self.slug, state, 11)
        self.assertLessEqual(len(context), MAX_CONTEXT)
        self.assertIn("EARLIER_SOURCE_ENDING_11", context)
        self.assertIn("EARLIER_SOURCE_ENDING_1", context)
        self.assertIn("The sealed vault", context)
        self.assertIn("seven rivers", context)
        self.assertNotIn("DO_NOT_SHARE_THIS", context)

    def test_revise_brief_changes_future_plan(self):
        self.setup_plan()
        updated = revise_chapter_brief(self.slug, 2, "New Crossing", "The harbor changes course.")
        self.assertEqual(updated["title"], "New Crossing")
        self.assertEqual(load_state(self.slug)["chapters"][1]["brief"], "The harbor changes course.")

    def test_external_model_is_rejected_without_call(self):
        self.setup_plan()
        for config in (
            ProviderConfig(provider="openai_compatible", base_url="https://api.vendor.com", model="remote"),
            ProviderConfig(provider="ollama", base_url="http://192.168.1.100:11434", model="off-device"),
        ):
            with patch("app.book_studio.generate_complete_prose", new_callable=AsyncMock) as generated:
                with self.assertRaisesRegex(ValueError, "loopback|local Ollama"):
                    asyncio.run(draft_next(self.slug, config))
                generated.assert_not_called()

    def test_draft_two_chapters_then_approve_without_overwriting_existing(self):
        self.setup_plan()
        sample = ("The captain checked her navigation chart, but the beacon answered in another language. " * 28).strip()
        async def fake_generation(*args, **kwargs):
            self.assertNotIn("DO_NOT_SHARE_THIS", str(args))
            return sample
        with patch("app.book_studio.generate_complete_prose", side_effect=fake_generation) as generator:
            one = asyncio.run(draft_next(self.slug, self.local))
            two = asyncio.run(draft_next(self.slug, self.local))
        self.assertEqual(generator.call_count, 2)
        self.assertEqual(one["chapter"]["number"], 1)
        self.assertEqual(two["chapter"]["number"], 2)
        self.assertEqual(load_state(self.slug)["chapters"][0]["status"], "candidate")
        self.assertIn("The captain checked", candidate(self.slug, 1)["content"])
        self.assertFalse((storage.project_root(self.slug) / "manuscript/book-studio/chapter-001.md").exists())
        # Author-created chapter must never be overwritten by a model candidate.
        path = storage.project_root(self.slug) / "manuscript/book-studio/chapter-001.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("AUTHOR MASTER TEXT", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            approve(self.slug, 1)
        self.assertEqual(path.read_text(encoding="utf-8"), "AUTHOR MASTER TEXT")
        approved = approve(self.slug, 2)
        self.assertEqual(approved["chapter"]["status"], "approved")
        self.assertIn("The captain checked", storage.read_text(self.slug, "manuscript/book-studio/chapter-002.md"))

    def test_edit_candidate_before_approval_preserves_original(self):
        self.setup_plan()
        sample = ("A visitor crossed the harbor while lanterns reflected beneath the floating islands. " * 30)
        with patch("app.book_studio.generate_complete_prose", new_callable=AsyncMock, return_value=sample):
            asyncio.run(draft_next(self.slug, self.local))
        original = candidate(self.slug, 1)["content"]
        edited = edit_candidate(self.slug, 1, original + "\nAuthor added a new ending!")
        self.assertIn("Author added", edited["content"])
        self.assertTrue(edited["chapter"]["edited_by_author"])
        backups = list((storage.project_root(self.slug) / ".ember" / "book-candidate-revisions" / "chapter-001").glob("*.md"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), original)
        approved = approve(self.slug, 1)
        self.assertEqual(approved["chapter"]["status"], "approved")
        self.assertIn("Author added", storage.read_text(self.slug, "manuscript/book-studio/chapter-001.md"))

    def test_author_reviews_local_outline_proposal(self):
        self.setup_plan()
        fake = '{"chapters":[{"title":"Signal","brief":"Discover a message and its consequences."},{"title":"Promise","brief":"The team chooses to share the truth."}]}'
        with patch("app.book_studio.generate", new_callable=AsyncMock, return_value=fake) as generated:
            result = asyncio.run(suggest_outline(self.slug, premise="A mysterious beacon", voice="Warm and clear",
                                                 chapter_count=2, config=self.local))
        self.assertEqual(len(result), 2)
        self.assertTrue(generated.called)
        self.assertEqual(load_state(self.slug)["chapters"][0]["title"], "Arrival")

    def test_decline_and_rebrief(self):
        self.setup_plan()
        sample = ("Far across the moons of the republic, the skyship opened its solar sails. " * 30)
        with patch("app.book_studio.generate_complete_prose", new_callable=AsyncMock, return_value=sample):
            asyncio.run(draft_next(self.slug, self.local))
        declined = decline(self.slug, 1)
        self.assertEqual(declined["status"], "failed")
        revised = revise_chapter_brief(self.slug, 1, "A gentler arrival", "An unfamiliar welcome.")
        self.assertEqual(revised["attempts"], 0)
        self.assertEqual(revised["status"], "planned")

    def test_api_contract_and_empty_private_isolation(self):
        client = TestClient(app)
        root = f"/api/projects/{self.slug}/book-studio"
        self.assertFalse(client.get(root).json()["configured"])
        response = client.put(root, json={"premise":"A shared discovery", "voice":"hopeful",
                                          "target_words": 300, "chapters": self.plan})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(client.get(f"/api/projects/{self.private['slug']}/book-studio").json()["chapters"], [])
        self.assertEqual(client.get("/api/projects/unknown/book-studio").status_code, 404)
        result = client.put(root + "/chapters/1", json={"title":"New Beginning", "brief":"A signal arrives."})
        self.assertEqual(result.status_code, 200, result.text)
        remote = client.post(root + "/draft-next", json={
            "provider": {"provider":"openai_compatible", "base_url":"https://external.example", "model":"external"}
        })
        self.assertEqual(remote.status_code, 400)
        self.assertIn("local Ollama", remote.text)


if __name__ == "__main__":
    unittest.main()
