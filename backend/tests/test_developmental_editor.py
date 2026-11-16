"""Synthetic-only Part 3 safety, data isolation, and manuscript editorial tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage
from app.developmental_editor import apply_paragraph_changes, chapters_report, document_report
from app.main import app


class DevelopmentalEditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        p = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        p.start()
        self.addCleanup(p.stop)
        self.slug = storage.create_project("Synthetic Editorial Book")["slug"]
        self.other = storage.create_project("Private Separate Book")["slug"]
        storage.save_text(self.other, "manuscript/secret.md", "PRIVATE_PROJECT_SECRET")
        self.text = (
            "# The Midnight Gate\n\nMira approached the gate. The wind was still.\n\n"
            "Tavi held the lantern, but Mira feared the harbor.\n\n"
            "The silent bell rang. The silent bell rang.\n"
        )
        storage.save_text(self.slug, "manuscript/01-gate.md", self.text)
        storage.save_text(self.slug, "manuscript/02-return.md",
                          "# Return\n\nMira returned to the gate. The silent bell rang again.\n")

    def test_health_report_is_evidence_based_and_project_scoped(self):
        report = chapters_report(self.slug, ["Mira", "Tavi"])
        self.assertEqual(report["chapter_count"], 2)
        self.assertEqual(len(report["subject_presence"]), 2)
        self.assertTrue(report["local_only"])
        self.assertNotIn("PRIVATE_PROJECT_SECRET", str(report))
        self.assertTrue(all("diagnostics" in ch for ch in report["chapters"]))

    def test_selective_revision_records_archive_and_preserves_other_paragraphs(self):
        doc = document_report(self.slug, "manuscript/01-gate.md")
        para = next(p for p in doc["paragraphs"] if p["text"].startswith("Tavi"))
        updated = "Tavi shielded the lantern; Mira watched the harbor in silence."
        outcome = apply_paragraph_changes(
            self.slug, doc["path"], doc["source_hash"],
            [{"id": para["id"], "replacement": updated}],
        )
        result = storage.read_text(self.slug, doc["path"])
        self.assertIn(updated, result)
        self.assertIn("The silent bell rang.", result)
        self.assertIn("# The Midnight Gate", result)
        self.assertIn(para["text"], self.text)
        self.assertNotIn(para["text"], result)
        self.assertTrue(outcome["snapshot_id"])
        self.assertEqual(len(document_report(self.slug, doc["path"])["revision_history"]), 2)

    def test_stale_source_and_duplicate_edits_are_rejected(self):
        doc = document_report(self.slug, "manuscript/01-gate.md")
        p = doc["paragraphs"][1]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            apply_paragraph_changes(
                self.slug, doc["path"], doc["source_hash"],
                [{"id": p["id"], "replacement": "A."}, {"id": p["id"], "replacement": "B."}],
            )
        storage.save_text(self.slug, doc["path"], self.text + "\nNew ending.")
        with self.assertRaisesRegex(ValueError, "changed since review"):
            apply_paragraph_changes(
                self.slug, doc["path"], doc["source_hash"],
                [{"id": p["id"], "replacement": "A."}],
            )
        self.assertIn("New ending.", storage.read_text(self.slug, doc["path"]))

    def test_no_cross_project_revisions_or_book_studio_candidate_edits(self):
        with self.assertRaises(ValueError):
            document_report(self.slug, "../other/manuscript/secret.md")
        with self.assertRaises(ValueError):
            document_report(self.slug, "manuscript/book-studio/chapter-001.md")
        self.assertEqual(storage.read_text(self.other, "manuscript/secret.md"),
                         "PRIVATE_PROJECT_SECRET")


    def test_dialogue_coach_traces_explicit_speech_tags_only(self):
        from app.developmental_editor import dialogue_report
        storage.save_text(
            self.slug, "manuscript/dialogue.md",
            '# The Argument\n\n"The harbor is safe," said Tavi.\n\n'
            '"I do not believe you," Mira replied.\n\n'
            '"Where is the compass?"\n\n'
            'Mira asked, "Do you remember the lighthouse?"\n',
        )
        report = dialogue_report(self.slug, "manuscript/dialogue.md")
        self.assertEqual(report["quote_count"], 4)
        self.assertEqual(report["attributed_count"], 3)
        self.assertEqual(report["unattributed_count"], 1)
        self.assertEqual({p["name"] for p in report["profiles"]},
                         {"Mira", "Tavi", "Unattributed"})
        with TestClient(app) as client:
            fetched = client.get(
                f"/api/projects/{self.slug}/developmental-editor/dialogue",
                params={"path": "manuscript/dialogue.md"},
            )
            self.assertEqual(fetched.status_code, 200, fetched.text)
            self.assertEqual(fetched.json()["quote_count"], 4)
            self.assertNotIn("PRIVATE_PROJECT_SECRET", str(fetched.json()))


    def test_explicit_rollback_rejects_stale_versions_and_restores_original(self):
        from app.developmental_editor import restore_document_version

        chapter = "manuscript/01-gate.md"
        first = document_report(self.slug, chapter)
        paragraph = next(p for p in first["paragraphs"] if p["text"].startswith("Tavi"))
        apply_paragraph_changes(
            self.slug, chapter, first["source_hash"],
            [{"id": paragraph["id"], "replacement": "Tavi abandoned the lantern."}],
        )
        updated = document_report(self.slug, chapter)
        previous = next(r for r in updated["revision_history"]
                        if r["source"] == "before-manual-edit")
        with self.assertRaisesRegex(ValueError, "changed since review"):
            restore_document_version(self.slug, chapter, first["source_hash"], previous["id"])
        restored = restore_document_version(self.slug, chapter, updated["source_hash"], previous["id"])
        self.assertEqual(restored["restored_from"], previous["id"])
        self.assertEqual(storage.read_text(self.slug, chapter), self.text)
        self.assertEqual(len(document_report(self.slug, chapter)["revision_history"]), 3)
        with TestClient(app) as client:
            saved = client.get(
                f"/api/projects/{self.slug}/developmental-editor/document",
                params={"path": chapter},
            ).json()
            stale = client.post(f"/api/projects/{self.slug}/developmental-editor/restore",
                                json={"path": chapter, "source_hash": updated["source_hash"],
                                      "revision_id": previous["id"]})
            self.assertEqual(stale.status_code, 409)
            self.assertEqual(saved["content"], self.text)

    def test_api_scan_document_apply_and_stale_conflict(self):
        with TestClient(app) as client:
            base = f"/api/projects/{self.slug}/developmental-editor"
            scan = client.get(base + "/overview", params={"subjects": "Mira"})
            self.assertEqual(scan.status_code, 200, scan.text)
            doc = client.get(base + "/document", params={"path": "manuscript/01-gate.md"}).json()
            p = next(p for p in doc["paragraphs"] if p["text"].startswith("Tavi"))
            payload = {"path": "manuscript/01-gate.md", "source_hash": doc["source_hash"],
                       "edits": [{"id": p["id"], "replacement": "Mira set the lantern down."}]}
            result = client.post(base + "/apply", json=payload)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()["edited_paragraphs"], 1)
            self.assertEqual(client.post(base + "/apply", json=payload).status_code, 409)


if __name__ == "__main__":
    unittest.main()
