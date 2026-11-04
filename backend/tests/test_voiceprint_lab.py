"""Offline author voice comparison: synthetic text, isolated projects."""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.voiceprint_lab import baseline, options, report, select


def sample(short=False):
    text = ("The navigator studied the darkening waves. "
            "The lanterns answered from the distant harbor! "
            "Mira raised her glasses and smiled. "
            "Would they reach the observatory before sunrise? " * 12)
    return text[:100] if short else text


class VoiceprintLabTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(gc.collect)
        fixture = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        fixture.start()
        self.addCleanup(fixture.stop)
        self.slug = storage.create_project("Synthetic Voice Studio")["slug"]
        self.other = storage.create_project("Other Private Novel")["slug"]
        storage.save_text(self.other, "style/secret.md", "ANOTHER_PRIVATE_PROJECT " * 100)
        storage.save_text(self.slug, "style/reference-sample.md", sample())
        storage.save_text(self.slug, "manuscript/chapter-001.md",
                          "# Chapter One\n\n" + ("He said it. She replied. The crew laughed. " * 45))

    def test_requires_real_reference_and_is_local(self):
        self.assertFalse(report(self.slug)["configured"])
        with self.assertRaisesRegex(ValueError, "reference"):
            select(self.slug, "style/../other/secret.md")
        with self.assertRaisesRegex(ValueError, "120 words"):
            select(self.slug, "style/author-profile.md")
        result = select(self.slug, "style/reference-sample.md")
        self.assertTrue(result["selected"])
        measured = report(self.slug)
        self.assertTrue(measured["configured"])
        self.assertEqual(measured["baseline"]["path"], "style/reference-sample.md")
        self.assertGreater(measured["reference"]["words"], 120)
        self.assertGreater(len(measured["chapters"]), 0)
        self.assertTrue(any(ch["signals"] for ch in measured["chapters"]))
        self.assertNotIn("ANOTHER_PRIVATE_PROJECT", str(measured))

    def test_author_edits_change_fingerprint_not_files(self):
        select(self.slug, "style/reference-sample.md")
        prior = report(self.slug)
        baseline_text = storage.read_text(self.slug, "style/reference-sample.md")
        storage.save_text(self.slug, "manuscript/chapter-001.md",
                          "# Chapter One\n\n" + ("A longer story unfolded beyond the valley. " * 60))
        newer = report(self.slug)
        self.assertNotEqual(prior["chapters"][0]["fingerprint"],
                            newer["chapters"][0]["fingerprint"])
        self.assertEqual(storage.read_text(self.slug, "style/reference-sample.md"), baseline_text)

    def test_api_contract(self):
        client = TestClient(app)
        base = f"/api/projects/{self.slug}/voiceprint"
        self.assertTrue(client.get(base + "/options").json())
        self.assertFalse(client.get(base + "/report").json()["configured"])
        response = client.put(base + "/reference", json={"path": "style/reference-sample.md"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(client.get(base + "/report").json()["configured"])
        self.assertEqual(client.get("/api/projects/missing/voiceprint/report").status_code, 404)
        bad = client.put(base + "/reference", json={"path": "../other/secret.md"})
        self.assertEqual(bad.status_code, 400)


if __name__ == "__main__":
    unittest.main()
