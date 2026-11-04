"""Author-owned release preflight with source-aware waivers; synthetic stories."""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage
from app.book_studio import configure
from app.main import app
from app.manuscript_intelligence import create_promise, update_promise
from app.production_preflight import markdown, preflight, restore, waive
from app.style_bible import add as add_style_rule, audit as style_audit, decide as decide_style


class ProductionPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(gc.collect)
        patcher = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.slug = storage.create_project("Synthetic Production Book")["slug"]
        self.other = storage.create_project("Synthetic Private Book")["slug"]
        storage.save_text(self.other, "manuscript/sensitive.md", "SENSITIVE_OTHER_PROJECT")
        storage.save_text(
            self.slug, "manuscript/chapter-001.md",
            "# Chapter One\n\nThe navigator discovered the the hidden lantern. "
            "The rest of the ship cheered. TODO: improve the ending.\n",
        )

    def test_content_and_book_plan_warnings(self):
        report = preflight(self.slug)
        codes = {item["code"] for item in report["issues"]}
        self.assertIn("very_short", codes)
        self.assertIn("editorial_marker", codes)
        self.assertIn("proofreading", codes)
        self.assertNotIn("SENSITIVE_OTHER_PROJECT", str(report))
        configure(self.slug, premise="Solve the lantern mystery", voice="Warm",
                  chapters=[{"title": "Arrival", "brief": "Track a hidden signal"}], target_words=300)
        updated = preflight(self.slug)
        codes = {item["code"] for item in updated["issues"]}
        self.assertIn("unapproved_chapters", codes)
        self.assertIn("unfinished_plan", codes)

    def test_open_story_promise_and_author_waiver(self):
        promise = create_promise(self.slug, "Mystery of the lantern", "hidden lantern")
        report = preflight(self.slug)
        issue = next(i for i in report["issues"] if i["code"] == "open_story_promise")
        self.assertFalse(issue["waived"])
        with self.assertRaisesRegex(ValueError, "specific"):
            waive(self.slug, issue["id"], "ok")
        next_report = waive(self.slug, issue["id"], "This mystery is intentionally left for book two.")
        decision = next(i for i in next_report["issues"] if i["id"] == issue["id"])
        self.assertTrue(decision["waived"])
        self.assertEqual(next_report["waived"], 1)
        restored = restore(self.slug, issue["id"])
        self.assertFalse(next(i for i in restored["issues"] if i["id"] == issue["id"])["waived"])
        update_promise(self.slug, promise["id"], "resolved", "The captain revealed the source.")
        self.assertFalse(any(i["code"] == "open_story_promise" for i in preflight(self.slug)["issues"]))

    def test_source_edit_invalidates_waiver(self):
        report = preflight(self.slug)
        issue = next(i for i in report["issues"] if i["code"] == "editorial_marker")
        waived = waive(self.slug, issue["id"], "The unfinished marker is part of the narrator's voice.")
        self.assertTrue(next(i for i in waived["issues"] if i["code"] == "editorial_marker")["waived"])
        storage.save_text(self.slug, "manuscript/chapter-001.md",
                          "# Chapter One\n\nThe captain turned toward the winter harbor. TODO: confirm starlight.\n")
        new = next(i for i in preflight(self.slug)["issues"] if i["code"] == "editorial_marker")
        self.assertFalse(new["waived"])

    def test_style_bible_findings_flow_to_release_gate(self):
        add_style_rule(self.slug, "avoid", "the the")
        warning = next(issue for issue in preflight(self.slug)["issues"] if issue["code"] == "style_bible")
        self.assertFalse(warning["waived"])
        finding = style_audit(self.slug)["findings"][0]
        decide_style(self.slug, finding["id"], "dismiss", "Deliberate speech repetition in dialogue.")
        self.assertFalse(any(i["code"] == "style_bible" for i in preflight(self.slug)["issues"]))

    def test_mechanical_prose_editor_findings_flow_to_preflight(self):
        from app.prose_editor import analyze, decide
        report = preflight(self.slug)
        self.assertTrue(any(item["code"] == "prose_editor" for item in report["issues"]))
        scan = analyze(self.slug, "manuscript/chapter-001.md")
        duplicate = next(item for item in scan["findings"] if item["rule"] == "double_word")
        decide(self.slug, "manuscript/chapter-001.md", duplicate["id"], scan["source_hash"],
               "dismiss", reason="Deliberate repetition in this prose passage.")
        self.assertFalse(any(item["code"] == "prose_editor" for item in preflight(self.slug)["issues"]))

    def test_api_reports_and_waivers_are_project_scoped(self):
        client = TestClient(app)
        root = f"/api/projects/{self.slug}/production-preflight"
        report = client.get(root)
        self.assertEqual(report.status_code, 200, report.text)
        self.assertEqual(client.get("/api/projects/missing/production-preflight").status_code, 404)
        self.assertEqual(client.get(root + "/report.md").status_code, 200)
        self.assertIn("Production Preflight", markdown(self.slug))
        issue = next(i for i in report.json()["issues"] if i["waivable"])
        w = client.post(root + "/waivers/" + issue["id"], json={
            "reason": "The author confirms this is intentional in this edition.",
        })
        self.assertEqual(w.status_code, 200, w.text)
        self.assertEqual(client.delete(root + "/waivers/" + issue["id"]).status_code, 200)
        self.assertNotIn("SENSITIVE_OTHER_PROJECT", client.get(root).text)


if __name__ == "__main__":
    unittest.main()
