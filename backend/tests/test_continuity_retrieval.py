"""Source grounded, bounded and project isolated context retrieval tests."""
from __future__ import annotations

import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import storage
from app.book_studio import _context, configure, load_state, MAX_CONTEXT
from app.continuity_retrieval import related_passages, context_section


class ContextEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(gc.collect)
        scope = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        scope.start()
        self.addCleanup(scope.stop)
        self.slug = storage.create_project("Synthetic Aster Context")["slug"]
        other = storage.create_project("Synthetic Private Context")["slug"]
        storage.save_text(other, "world/other.md", "DO_NOT_RETRIEVE_PROJECT_B")
        self.chapters = [
            {"title": "The Gate", "brief": "Mara carries a copper compass to the crossing"},
            {"title": "The Lantern", "brief": "The city lantern is lost"},
            {"title": "Forgotten Crossing", "brief": "Mara rediscovers the copper compass during the crossing and remembers the vow"},
        ]
        configure(self.slug, premise="The valley has a hidden gate", voice="Close third",
                  chapters=self.chapters, target_words=300)
        root = storage.project_root(self.slug) / ".ember" / "book-candidates"
        root.mkdir(parents=True, exist_ok=True)
        (root / "chapter-001.md").write_text(
            "# The Gate\n\n"
            "A distant gate sounded across the valley. The watchmen checked the guard posts.\n\n"
            "Mara placed the copper compass in a sealed wooden box, promising she would "
            "never cross the river until her brother returned. She whispered an old vow "
            "and carved the word remembrance into the lid.\n\n"
            "The travelers departed before midnight and left their lantern burning.",
            encoding="utf-8",
        )
        (root / "chapter-002.md").write_text(
            "# The Lantern\n\n"
            "The city lantern guttered, and the crowd gathered below the tower. "
            "The market closed by midnight. " * 10,
            encoding="utf-8",
        )
        state = load_state(self.slug)
        for chapter in state["chapters"][:2]:
            chapter["status"] = "candidate"
        self.state = state

    def test_retrieves_interiors_with_source_attribution(self):
        results = related_passages(self.slug, self.state, 2)
        self.assertEqual(results[0]["chapter"], 1)
        self.assertGreater(results[0]["line"], 1)
        self.assertIn("copper compass", results[0]["excerpt"])
        self.assertIn("Mara", results[0]["excerpt"])
        self.assertNotIn("DO_NOT_RETRIEVE_PROJECT_B", str(results))
        section = context_section(self.slug, self.state, 2)
        self.assertIn("verbatim", section)
        self.assertIn("source line", section)
        context = _context(self.slug, self.state, 2)
        self.assertIn("copper compass", context)
        self.assertLessEqual(len(context), MAX_CONTEXT)

    def test_no_ai_inference_and_no_future_chapter_leak(self):
        self.assertEqual(related_passages(self.slug, self.state, 1), [])
        original = self.state["chapters"][0]["status"]
        self.state["chapters"][0]["status"] = "failed"
        self.assertEqual(related_passages(self.slug, self.state, 2), [])
        self.state["chapters"][0]["status"] = original
        self.state["chapters"][2]["brief"] = "The hero finds an unrelated sapphire phoenix"
        self.assertEqual(related_passages(self.slug, self.state, 2), [])

    def test_excerpt_budget_and_chapter_diversity(self):
        root = storage.project_root(self.slug) / ".ember" / "book-candidates"
        (root / "chapter-001.md").write_text(
            "# The Gate\n\n" + ("Mara used the copper compass to cross the stormy river. " * 2000),
            encoding="utf-8",
        )
        items = related_passages(self.slug, self.state, 2)
        self.assertEqual(len(items), 1)
        self.assertLessEqual(len(items[0]["excerpt"]), 520)
        self.assertLessEqual(len(_context(self.slug, self.state, 2)), MAX_CONTEXT)


if __name__ == "__main__":
    unittest.main()
