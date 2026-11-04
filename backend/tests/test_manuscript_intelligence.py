"""Novel-wide, project-scoped evidence tests with synthetic chapters only."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import storage
from app.manuscript_intelligence import analyze, create_promise, update_promise
from app.main import app


class ManuscriptIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.slug = storage.create_project("Synthetic Lighthouse Chronicle")["slug"]
        self.other = storage.create_project("Sensitive Other Project")["slug"]
        storage.save_text(self.other, "manuscript/secret.md",
                          "PRIVATE_OTHER_PROJECT never appears in the scanned story.")
        storage.save_text(self.slug, "manuscript/01-arrival.md",
                          "# Arrival\nMira followed the glass compass. Mira found a hidden lantern. "
                          "The hidden lantern was on a boat.\n"
                          "The captain spoke about the glass compass, then hid it.\n")
        storage.save_text(self.slug, "manuscript/02-crossing.md",
                          "# Crossing\nMira followed the glass compass. Tavi crossed the harbor. "
                          "The hidden lantern was on a boat. The compass remained hidden.\n")

    def test_novel_scan_is_local_and_evidence_bound(self):
        report = analyze(self.slug, ["Mira", "Tavi"])
        self.assertEqual(report["chapter_count"], 2)
        self.assertGreater(report["total_words"], 20)
        self.assertIn("Mira", [item["name"] for item in report["chapters"][0]["tracked_subjects"]])
        self.assertNotIn("Tavi", [item["name"] for item in report["chapters"][0]["tracked_subjects"]])
        self.assertIn("Tavi", [item["name"] for item in report["chapters"][1]["tracked_subjects"]])
        self.assertNotIn("PRIVATE_OTHER_PROJECT", str(report))
        self.assertIn("presence is not character agency", report["limitations"])

    def test_promise_is_author_controlled_not_auto_resolved(self):
        promise = create_promise(self.slug, "Competing lantern promises", "glass compass",
                                 "Reveal the maker in the last act.")
        report = analyze(self.slug)
        self.assertEqual(report["promises"][0]["reference_count"], 2)
        self.assertFalse(report["promises"][0]["automatically_resolved"])
        self.assertEqual(report["promises"][0]["status"], "open")
        updated = update_promise(self.slug, promise["id"], "resolved", "Revealed at the tower.")
        self.assertEqual(updated["status"], "resolved")
        self.assertEqual(analyze(self.slug)["promises"][0]["resolution_note"], "Revealed at the tower.")
        with self.assertRaises(ValueError):
            update_promise(self.slug, promise["id"], "invented")

    def test_cross_chapter_echoes_and_book_candidates_not_double_counted(self):
        report = analyze(self.slug)
        echoes = {item["phrase"] for item in report["cross_chapter_echoes"]}
        self.assertIn("the hidden lantern was", echoes)
        from app.book_studio import configure, draft_next, approve
        from app.models import ProviderConfig
        from unittest.mock import AsyncMock
        import asyncio
        configure(self.slug, premise="A new journey", voice="Warm third person",
                  target_words=300, chapters=[{"title": "New Light", "brief": "The lantern is restored."}])
        writing = "Mira found the glass compass and promised to return it. " * 35
        provider = ProviderConfig(provider="ollama", base_url="http://127.0.0.1:11434", model="synthetic")
        with patch("app.book_studio.generate_complete_prose", new_callable=AsyncMock, return_value=writing):
            asyncio.run(draft_next(self.slug, provider))
        before = analyze(self.slug)
        self.assertEqual(before["chapter_count"], 3)
        self.assertEqual(sum(ch["status"] == "candidate" for ch in before["chapters"]), 1)
        approve(self.slug, 1)
        after = analyze(self.slug)
        self.assertEqual(after["chapter_count"], 3)
        self.assertEqual(sum(ch["status"] == "approved" for ch in after["chapters"]), 1)

    def test_project_isolation_and_invalid_subjects(self):
        self.assertEqual(analyze(self.other)["chapter_count"], 1)
        self.assertEqual(analyze(self.slug)["chapter_count"], 2)
        with self.assertRaises(ValueError):
            analyze(self.slug, ["x"])
        with self.assertRaises(ValueError):
            analyze(self.slug, ["name"] * 31)

    def test_api(self):
        client = TestClient(app)
        base = f"/api/projects/{self.slug}/manuscript-intelligence"
        report = client.get(base + "/analyze", params={"subjects": "Mira"})
        self.assertEqual(report.status_code, 200, report.text)
        self.assertEqual(report.json()["chapter_count"], 2)
        self.assertEqual(client.get("/api/projects/unknown/manuscript-intelligence/analyze").status_code, 404)
        added = client.post(base + "/promises", json={"title": "The secret", "tracking_phrase": "glass compass"})
        self.assertEqual(added.status_code, 201, added.text)
        changed = client.patch(base + "/promises/" + added.json()["id"],
                               json={"status": "resolved", "resolution_note": "Revealed in the story"})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(client.get(base + "/promises").json()[0]["status"], "resolved")


if __name__ == "__main__":
    unittest.main()
