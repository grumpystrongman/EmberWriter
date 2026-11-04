from __future__ import annotations

import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage
from app.autopilot import audit_history, current_readiness, run_audit
from app.main import app


class AutopilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name) / "projects"
        self.patcher = patch.object(storage, "PROJECTS_ROOT", root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        # The legacy save_text helper leaves SQLite handles to GC; Windows
        # requires they be collected before removing temporary test folders.
        self.addCleanup(gc.collect)
        self.project = storage.create_project("Autopilot Sample")
        self.slug = self.project["slug"]
        storage.save_text(self.slug, "characters/lyra.md", "# Lyra\nA careful navigator.")
        storage.save_text(self.slug, "world/arcadia.md", "# Arcadia\nFloating islands.")
        storage.save_text(self.slug, "scenes/first-meeting.md", "# Scene\nThe protagonists meet.")
        storage.save_text(self.slug, "style/story-style.md", "# Voice\nVivid, sincere and concise.")
        storage.save_text(self.slug, "manuscript/chapter-001.md",
                          "# Chapter One\n\n" + ("The captain consulted the map. The engineer checked the lights. " * 12))

    def test_readiness_is_non_destructive_and_local(self):
        original = storage.read_text(self.slug, "manuscript/chapter-001.md")
        result = current_readiness(self.slug)
        self.assertEqual(result["foundation_complete"], 4)
        self.assertTrue(result["local_only"])
        self.assertFalse(result["manuscript_modified"])
        self.assertEqual(result["drafted_count"], 1)
        self.assertEqual(storage.read_text(self.slug, "manuscript/chapter-001.md"), original)
        self.assertFalse((storage.project_root(self.slug) / ".ember" / "autopilot-audits.json").exists())

    def test_history_is_local_and_limited(self):
        first = run_audit(self.slug)
        self.assertIn("fingerprint", first)
        self.assertEqual(len(audit_history(self.slug)), 1)
        path = storage.project_root(self.slug) / ".ember" / "autopilot-audits.json"
        self.assertIn(first["id"], path.read_text(encoding="utf-8"))
        for _ in range(22):
            run_audit(self.slug)
        self.assertEqual(len(audit_history(self.slug)), 20)

    def test_routes_respond_and_unknown_project_is_404(self):
        client = TestClient(app)
        response = client.get(f"/api/projects/{self.slug}/autopilot/readiness")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(client.get(f"/api/projects/{self.slug}/autopilot/audits").json()), 0)
        created = client.post(f"/api/projects/{self.slug}/autopilot/audits")
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(len(client.get(f"/api/projects/{self.slug}/autopilot/audits").json()), 1)
        self.assertEqual(client.get("/api/projects/missing/autopilot/readiness").status_code, 404)

    def test_private_projects_never_enter_another_project_report(self):
        private = storage.create_project("Private Invisible Project")
        storage.save_text(private["slug"], "manuscript/chapter-001.md",
                          "TOP SECRET OTHER PROJECT should not be accessed")
        result = run_audit(self.slug)
        payload = json.dumps(result)
        self.assertNotIn("TOP SECRET", payload)
        self.assertNotIn(private["slug"], payload)

    def test_foreshadowing_debt_uses_author_owned_thread_state(self):
        storage.save_text(self.slug, "planning/story-development.json", json.dumps({
            "threads": [{"id": "thread-lantern", "title": "Who lit the lantern?",
                         "status": "open", "setup": "A mysterious lantern appeared."}]
        }))
        report = current_readiness(self.slug)
        self.assertEqual(report["open_threads"], 1)
        self.assertEqual(report["unplanned_payoffs"], ["Who lit the lantern?"])
        self.assertTrue(any("1 unresolved story promise" in item
                            for item in report["phases"][0]["tasks"]))
