"""Whole-book editorial scans and atomic author-approved corrections."""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage
from app.editorial_board import apply, freshness, history, markdown, preview, report, scan
from app.main import app
from app.prose_editor import decide as dismiss_prose
from app.style_bible import add as add_rule


class EditorialBoardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.addCleanup(gc.collect)
        fixture = patch.object(storage, "PROJECTS_ROOT", Path(temp.name) / "projects")
        fixture.start()
        self.addCleanup(fixture.stop)
        self.slug = storage.create_project("Synthetic Editorial Novel")["slug"]
        other = storage.create_project("Private Other Project")["slug"]
        storage.save_text(other, "manuscript/private.md", "NO_PRIVATE_DATA_HERE")
        self.chapter = "manuscript/chapter-001.md"
        self.original = ("# Arrival\n\n"
                         "The crew could of arrived earlier. Mira saw the the lantern. "
                         "Everyone walked into Aster Fall  quietly.\n")
        storage.save_text(self.slug, self.chapter, self.original)
        self.second = "manuscript/chapter-002.md"
        storage.save_text(self.slug, self.second,
                          "# Return\n\nThe crew would of returned to Aster Fall. The watchman stood at the gate.\n")
        add_rule(self.slug, "preferred", "Aster Fall", "Asterfall")

    def test_scan_aggregates_tools_and_keeps_projects_isolated(self):
        result = scan(self.slug, "third", "past")
        self.assertEqual(result["chapter_count"], 2)
        self.assertGreaterEqual(result["outstanding"], 6)
        self.assertGreaterEqual(result["fixable"], 4)
        self.assertEqual(len(history(self.slug)), 1)
        self.assertNotIn("NO_PRIVATE_DATA_HERE", str(result))
        self.assertIn("Aster Fall", markdown(self.slug))
        self.assertEqual(storage.read_text(self.slug, self.chapter), self.original)
        self.assertTrue(any(item["origin"] == "style" for ch in result["chapters"] for item in ch["findings"]))
        self.assertTrue(any(item["origin"] == "prose" for ch in result["chapters"] for item in ch["findings"]))

    def test_preview_is_read_only_apply_is_one_snapshot(self):
        board = scan(self.slug)
        chapter = next(ch for ch in board["chapters"] if ch["path"] == self.chapter)
        options = [item["id"] for item in chapter["findings"] if item["mechanical"] and item["category"] in ("modal_of", "double_word")]
        self.assertEqual(len(options), 2)
        draft = preview(self.slug, self.chapter, options, chapter["fingerprint"])
        self.assertEqual(draft["count"], 2)
        self.assertIn("could have arrived", draft["proposed"])
        self.assertIn("saw the lantern", draft["proposed"])
        self.assertEqual(storage.read_text(self.slug, self.chapter), self.original)
        prior_snapshots = len(storage.list_snapshots(self.slug, self.chapter))
        result = apply(self.slug, self.chapter, options, chapter["fingerprint"], draft["proposed_hash"])
        self.assertTrue(result["applied"])
        self.assertEqual(len(storage.list_snapshots(self.slug, self.chapter)), prior_snapshots + 1)
        self.assertEqual(storage.read_text(self.slug, self.chapter), draft["proposed"])
        with self.assertRaisesRegex(ValueError, "changed"):
            apply(self.slug, self.chapter, options, chapter["fingerprint"], draft["proposed_hash"])
        self.assertEqual(report(self.slug)["chapters"][0]["fixable"], chapter["fixable"] - 2)

    def test_reject_stale_overlapping_and_nonmechanical_actions(self):
        board = scan(self.slug)
        chapter = next(ch for ch in board["chapters"] if ch["path"] == self.chapter)
        mechanical = [item["id"] for item in chapter["findings"] if item["mechanical"]]
        style = next(item["id"] for item in chapter["findings"] if item["origin"] == "style")
        with self.assertRaisesRegex(ValueError, "mechanical"):
            preview(self.slug, self.chapter, [style], chapter["fingerprint"])
        with self.assertRaisesRegex(ValueError, "distinct"):
            preview(self.slug, self.chapter, [mechanical[0]] * 2, chapter["fingerprint"])
        storage.save_text(self.slug, self.chapter, self.original + "\nAn author-written extra scene.")
        with self.assertRaisesRegex(ValueError, "changed"):
            preview(self.slug, self.chapter, [mechanical[0]], chapter["fingerprint"])

    def test_dismissals_propagate_to_board(self):
        before = scan(self.slug)
        ch = next(x for x in before["chapters"] if x["path"] == self.chapter)
        issue = next(x for x in ch["findings"] if x["origin"] == "prose" and x["category"] == "modal_of")
        dismiss_prose(self.slug, ch["path"], issue["id"].removeprefix("prose:"), ch["fingerprint"],
                      "dismiss", reason="The narrator is deliberately using regional dialect.")
        after = report(self.slug)
        matching = next(x for x in after["chapters"][0]["findings"] if x["id"] == issue["id"])
        self.assertEqual(matching["decision"], "dismissed")
        self.assertEqual(after["fixable"], before["fixable"] - 1)

    def test_edit_after_scan_requires_a_new_baseline(self):
        self.assertFalse(freshness(self.slug)["scanned"])
        scan(self.slug)
        self.assertTrue(freshness(self.slug)["current"])
        storage.save_text(self.slug, self.chapter, self.original + "\nA new paragraph follows.")
        changed = freshness(self.slug)
        self.assertFalse(changed["current"])
        self.assertEqual(changed["changed"], [self.chapter])
        scan(self.slug)
        self.assertTrue(freshness(self.slug)["current"])

    def test_unapproved_book_studio_candidate_is_editable_but_not_approved(self):
        import asyncio
        from unittest.mock import AsyncMock

        from app.book_studio import candidate, configure, draft_next, load_state
        from app.models import ProviderConfig
        configure(self.slug, premise="A lantern guides a lost ship", voice="Quiet maritime prose",
                  target_words=300,
                  chapters=[{"title": "Signal", "brief": "The captain returns to harbor"}])
        story = ("The captain could of returned before midnight. "
                 "The sailors saw the the distant beacon. " * 40)
        provider = ProviderConfig(provider="ollama", base_url="http://127.0.0.1:11434",
                                  model="fictional-local-model")
        with patch("app.book_studio.generate_complete_prose", new_callable=AsyncMock, return_value=story):
            asyncio.run(draft_next(self.slug, provider))
        first = candidate(self.slug, 1)["content"]
        board = scan(self.slug)
        chapter = next(ch for ch in board["chapters"] if ch["path"] == "book-studio:candidate:1")
        selected = [x["id"] for x in chapter["findings"] if x["mechanical"]][:2]
        proposed = preview(self.slug, chapter["path"], selected, chapter["fingerprint"])
        changed = apply(self.slug, chapter["path"], selected, chapter["fingerprint"], proposed["proposed_hash"])
        self.assertTrue(changed["applied"])
        self.assertNotEqual(candidate(self.slug, 1)["content"], first)
        self.assertEqual(load_state(self.slug)["chapters"][0]["status"], "candidate")
        archived = list((storage.project_root(self.slug) / ".ember" / "book-candidate-revisions"
                         / "chapter-001").glob("*.md"))
        self.assertTrue(archived)
        self.assertEqual(archived[-1].read_text(encoding="utf-8"), first)

    def test_reader_and_arc_coverage_are_current_only(self):
        import asyncio
        import json
        from unittest.mock import AsyncMock

        from app.book_reviews import evaluate
        from app.book_studio import candidate, configure, draft_next, edit_candidate
        from app.models import ProviderConfig
        from app.story_arc_investigator import inspect
        configure(self.slug, premise="The strange beacon", voice="Close third",
                  target_words=300, chapters=[{"title": "Night", "brief": "Return to the lighthouse."}])
        text = ("Mira turned the ship toward the beacon. The watchman studied the horizon. " * 36)
        model = ProviderConfig(provider="ollama", base_url="http://127.0.0.1:11434", model="local-test")
        with patch("app.book_studio.generate_complete_prose", new_callable=AsyncMock, return_value=text):
            asyncio.run(draft_next(self.slug, model))
        review = json.dumps({
            "verdict": "Readers follow Mira's clear decision.",
            "scores": {"engagement": 4, "clarity": 4, "pacing": 3, "character": 4, "voice": 4},
            "strengths": ["Clear opening"], "findings": [],
        })
        with patch("app.book_reviews.generate", new_callable=AsyncMock, return_value=review):
            asyncio.run(evaluate(self.slug, 1, "genre_fan", model))
        arcs = json.dumps({
            "summary": "Mira heads toward the beacon.", "tension": 3,
            "events": [{"kind": "choice", "label": "Beacon decision", "subject": "Mira",
                        "quote": "Mira turned the ship toward the beacon.",
                        "meaning": "Mira changes the ship's course."}],
        })
        with patch("app.story_arc_investigator.generate", new_callable=AsyncMock, return_value=arcs):
            asyncio.run(inspect(self.slug, "book-studio:candidate:1", model))
        before = report(self.slug)
        chapter = next(x for x in before["chapters"] if x["path"] == "book-studio:candidate:1")
        self.assertEqual(chapter["reader_reviews"], 1)
        self.assertTrue(chapter["story_arc_reviewed"])
        self.assertEqual(before["reader_coverage"], 1)
        self.assertEqual(before["story_arc_coverage"], 1)
        edit_candidate(self.slug, 1, candidate(self.slug, 1)["content"] + "\nAn author alteration.")
        after = report(self.slug)
        revised = next(x for x in after["chapters"] if x["path"] == "book-studio:candidate:1")
        self.assertEqual(revised["reader_reviews"], 0)
        self.assertFalse(revised["story_arc_reviewed"])

    def test_api_preview_and_export(self):
        client = TestClient(app)
        root = f"/api/projects/{self.slug}/editorial-board"
        self.assertEqual(client.get(root + "/history").json(), [])
        self.assertFalse(client.get(root + "/freshness").json()["scanned"])
        board_response = client.post(root + "/scan", json={"perspective": "third", "tense": "past"})
        self.assertEqual(board_response.status_code, 200, board_response.text)
        data = board_response.json()
        chapter = next(ch for ch in data["chapters"] if ch["path"] == self.chapter)
        option = next(i for i in chapter["findings"] if i["mechanical"])
        response = client.post(root + "/preview", json={
            "path": chapter["path"], "ids": [option["id"]],
            "source_hash": chapter["fingerprint"], "perspective": "third", "tense": "past",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(client.get(root + "/report.md").status_code, 200)
        self.assertEqual(client.post(root + "/preview", json={
            "path": "../private.md", "ids": [option["id"]], "source_hash": chapter["fingerprint"]
        }).status_code, 404)


if __name__ == "__main__":
    unittest.main()
