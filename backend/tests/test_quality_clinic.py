"""Private, transparent writing-quality diagnostics tests."""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.quality_clinic import check_text


class QualityClinicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(gc.collect)
        self.patch = patch.object(storage, "PROJECTS_ROOT", Path(self.tmp.name) / "projects")
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.slug = storage.create_project("Synthetic Grammar Project")["slug"]
        self.other = storage.create_project("Private Other Project")["slug"]
        storage.save_text(self.other, "manuscript/top-secret.md", "TOP SECRET PERSONAL CHAPTER")
        storage.save_text(self.slug, "manuscript/chapter-001.md",
                          "In that moment the the captain knew it was as if the city had changed.\n"
                          "She was informed, and she was warned.  Too many  spaces!!!\n")

    def test_grammar_slop_and_words_have_explanations(self):
        findings = check_text(storage.read_text(self.slug, "manuscript/chapter-001.md"))
        self.assertGreater(findings["metrics"]["words"], 5)
        categories = {finding["category"] for finding in findings["findings"]}
        self.assertIn("proofreading", categories)
        self.assertIn("AI-pattern", categories)
        self.assertIn("punctuation", categories)
        self.assertFalse(any("TOP SECRET" in str(item) for item in findings["findings"]))

    def test_api_is_project_scoped_and_read_only(self):
        client = TestClient(app)
        path = "manuscript/chapter-001.md"
        original = storage.read_text(self.slug, path)
        root = f"/api/projects/{self.slug}/quality-clinic"
        response = client.get(root + "/inspect", params={"path": path})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["path"], path)
        self.assertEqual(client.get(root + "/inspect", params={"path": "../top-secret.md"}).status_code, 400)
        self.assertEqual(client.get("/api/projects/missing/quality-clinic/chapters").status_code, 404)
        self.assertEqual(storage.read_text(self.slug, path), original)


if __name__ == "__main__":
    unittest.main()
