"""Non-destructive, version-aware prose editing with synthetic material."""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage
from app.prose_editor import analyze, decide, sources
from app.main import app


class ProseEditorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(gc.collect)
        patcher = patch.object(storage, "PROJECTS_ROOT", Path(tmp.name) / "projects")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.slug = storage.create_project("Fictional Grammar Trial")["slug"]
        other = storage.create_project("Other Private Fiction")["slug"]
        storage.save_text(other, "manuscript/secret.md", "DO_NOT_INCLUDE_THIS_PROJECT")
        self.path = "manuscript/chapter-001.md"
        self.original = (
            "# First Watch\n\n"
            "Mira could of returned. She walked to the the station  , and looked up.\n"
            "I saw the lantern and knew its secret, although this chapter uses third person narration.\n"
            "The captain walks through the city, looks at the tower, says nothing, turns east, and runs uphill.\n"
        )
        storage.save_text(self.slug, self.path, self.original)

    def test_corrections_are_exact_and_explicit(self):
        report = analyze(self.slug, self.path, "third", "past")
        names = {row["rule"] for row in report["findings"]}
        self.assertTrue({"modal_of", "double_word", "space_punctuation", "pov", "tense"} <= names)
        self.assertNotIn("DO_NOT_INCLUDE_THIS_PROJECT", str(report))
        self.assertEqual(storage.read_text(self.slug, self.path), self.original)
        modal = next(row for row in report["findings"] if row["rule"] == "modal_of")
        self.assertEqual(modal["suggested"], "could have")
        changed = decide(self.slug, self.path, modal["id"], report["source_hash"], "apply", "third", "past")
        self.assertTrue(changed["applied"])
        self.assertIn("could have returned", storage.read_text(self.slug, self.path))
        self.assertNotIn("could of returned", storage.read_text(self.slug, self.path))
        snapshots = storage.list_snapshots(self.slug, self.path)
        self.assertTrue(snapshots)
        self.assertNotIn("DO_NOT_INCLUDE_THIS_PROJECT", str(changed))
        with self.assertRaisesRegex(ValueError, "edited since"):
            decide(self.slug, self.path, modal["id"], report["source_hash"], "apply", "third", "past")

    def test_common_typo_suggestions_remain_author_controlled(self):
        storage.save_text(self.slug, self.path,
                          "# Fictional Page\n\nThe traveler would definately recieve a seperate map.\n")
        report = analyze(self.slug, self.path)
        findings = [item for item in report["findings"] if item["rule"] == "lexical_typo"]
        self.assertEqual({item["suggested"] for item in findings},
                         {"definitely", "receive", "separate"})
        self.assertIn("definately", storage.read_text(self.slug, self.path))
        selected = next(item for item in findings if item["suggested"] == "definitely")
        decision = decide(self.slug, self.path, selected["id"], report["source_hash"], "apply")
        self.assertTrue(decision["applied"])
        self.assertIn("definitely", storage.read_text(self.slug, self.path))
        self.assertTrue(storage.list_snapshots(self.slug, self.path))

    def test_dismiss_and_invalidate_after_edit(self):
        report = analyze(self.slug, self.path, "third", "past")
        finding = next(row for row in report["findings"] if row["rule"] == "pov")
        with self.assertRaisesRegex(ValueError, "8"):
            decide(self.slug, self.path, finding["id"], report["source_hash"], "dismiss", "third", "past", "okay")
        dismissed = decide(self.slug, self.path, finding["id"], report["source_hash"], "dismiss",
                           "third", "past", "A brief first-person memory is intentional.")
        self.assertEqual(next(row for row in dismissed["findings"] if row["id"] == finding["id"])["decision"], "dismissed")
        reopened = decide(self.slug, self.path, finding["id"], report["source_hash"], "reopen", "third", "past")
        self.assertEqual(next(row for row in reopened["findings"] if row["id"] == finding["id"])["decision"], "pending")
        decide(self.slug, self.path, finding["id"], report["source_hash"], "dismiss", "third", "past", "Intended narrative intrusion.")
        storage.save_text(self.slug, self.path, self.original + "A new ending unfolds.\n")
        new = analyze(self.slug, self.path, "third", "past")
        self.assertFalse(any(row["decision"] == "dismissed" for row in new["findings"]))
        with self.assertRaisesRegex(ValueError, "edited since"):
            decide(self.slug, self.path, finding["id"], report["source_hash"], "reopen", "third", "past")

    def test_subjective_pov_and_tense_not_autocorrected(self):
        report = analyze(self.slug, self.path, "third", "past")
        warning = next(f for f in report["findings"] if f["rule"] == "tense")
        self.assertIsNone(warning["suggested"])
        with self.assertRaisesRegex(ValueError, "subjective"):
            decide(self.slug, self.path, warning["id"], report["source_hash"], "apply", "third", "past")
        self.assertEqual(storage.read_text(self.slug, self.path), self.original)

    def test_api_validation_and_project_isolation(self):
        client = TestClient(app)
        root = f"/api/projects/{self.slug}/prose-editor"
        self.assertEqual(len(client.get(root + "/chapters").json()), 1)
        self.assertEqual(client.get("/api/projects/unknown/prose-editor/chapters").status_code, 404)
        examined = client.post(root + "/inspect", json={
            "path": self.path, "perspective": "third", "tense": "past",
        })
        self.assertEqual(examined.status_code, 200, examined.text)
        self.assertEqual(examined.json()["path"], self.path)
        self.assertEqual(client.post(root + "/inspect", json={"path": "../secret.md"}).status_code, 404)
        self.assertEqual(client.post(root + "/inspect", json={"path": self.path, "tense": "mixed"}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
