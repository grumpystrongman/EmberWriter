"""Source-provenance continuity regression using artificial chapter facts."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

from app import storage, memory
from app.continuity_audit import audit, find_conflicts
from app.main import app


def fact(kind, subject, predicate, obj, chapter, order=1):
    return {"kind": kind, "subject": subject, "predicate": predicate, "object": obj,
            "source_path": chapter, "chapter_order": order, "confidence": .97}


class ContradictionCandidates(unittest.TestCase):
    def test_static_dates_and_character_knowledge_without_false_movement(self):
        f = [
            fact("canon", "Mira", "birthplace", "Eastport", "manuscript/001.md", 1),
            fact("canon", "Mira", "born in", "Westport", "manuscript/004.md", 4),
            fact("timeline", "Great Storm", "occurred on", "April 3, 2027", "manuscript/002.md", 2),
            fact("timeline", "Great Storm", "date", "April 4, 2027", "manuscript/005.md", 5),
            fact("location", "Mira", "located at", "Eastport", "manuscript/001.md", 1),
            fact("location", "Mira", "located at", "Westport", "manuscript/004.md", 4),
            fact("character_knowledge", "Mira", "knows", "The captain's identity", "manuscript/002.md", 2),
            fact("character_knowledge", "Mira", "does not know", "The captain's identity", "manuscript/005.md", 5),
        ]
        conflicts = find_conflicts(f)
        self.assertEqual({row["type"] for row in conflicts},
                         {"static_fact_conflict", "date_conflict", "knowledge_reversal_review"})
        self.assertTrue(all(row["earlier"]["source_path"].startswith("manuscript/")
                            and row["later"]["source_path"].startswith("manuscript/")
                            for row in conflicts))

    def test_freshness_reconciliation_removes_stale_chapter_facts(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            with patch.object(storage, "PROJECTS_ROOT", Path(tmp) / "projects"):
                slug = storage.create_project("Synthetic Retcon")[ "slug" ]
                p1, p2 = "manuscript/001.md", "manuscript/002.md"
                storage.save_text(slug, p1, "# Chapter One\n\nMira came from Eastport.")
                storage.save_text(slug, p2, "# Chapter Two\n\nMira was born in Westport.")
                memory.store_analysis(slug, p1, storage.read_text(slug, p1),
                                      {"summary": "Origin", "facts": [{"kind": "canon",
                                       "subject": "Mira", "predicate": "birthplace", "object": "Eastport"}]})
                memory.store_analysis(slug, p2, storage.read_text(slug, p2),
                                      {"summary": "Conflicting origin", "facts": [{"kind": "canon",
                                       "subject": "Mira", "predicate": "born in", "object": "Westport"}]})
                self.assertEqual(len(audit(slug)["candidates"]), 1)
                response = TestClient(app).get(f"/api/projects/{slug}/memory/continuity-audit")
                self.assertEqual(response.status_code, 200, response.text)
                storage.save_text(slug, p2, "# Revised Chapter\n\nMira traveled to Westport.")
                fresh = audit(slug)
                self.assertEqual(fresh["candidates"], [])
                self.assertEqual(fresh["stale_analyses_removed"], 1)
                self.assertTrue(storage.read_text(slug, p2).endswith("Westport."))


if __name__ == "__main__":
    unittest.main()
