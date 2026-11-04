from __future__ import annotations

import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage
from app.canon_ripple import create_ripple, find_impacts, list_ripples, update_ripple
from app.main import app


class CanonRippleTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.addCleanup(gc.collect)
        self.patcher = patch.object(storage, "PROJECTS_ROOT", Path(self.folder.name) / "projects")
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.project = storage.create_project("Synthetic lighthouse story")
        self.slug = self.project["slug"]
        self.other = storage.create_project("Personal library must never be read")
        storage.save_text(self.slug, "characters/captain.md",
                          "# Captain Ada\nAda was born on Luna.")
        storage.save_text(self.slug, "manuscript/chapter-001.md",
                          "# First Flight\nAda was born on Luna. She recalls Luna fondly.")
        storage.save_text(self.slug, "world/moons.md",
                          "# Colony Map\nOur records state Ada was born on Luna.")
        storage.save_text(self.other["slug"], "manuscript/chapter-001.md",
                          "TOP SECRET: Ada was born on Luna.\n")

    def new(self):
        return create_ripple(self.slug, title="Ada birthplace", old_fact="Ada was born on Luna",
                             proposed_fact="Ada was born on Mars",
                             source_path="characters/captain.md", rationale="Better fits the route map.")

    def test_impact_is_local_bounded_and_non_mutating(self):
        before = storage.read_text(self.slug, "manuscript/chapter-001.md")
        item = self.new()
        self.assertEqual(item["status"], "proposed")
        self.assertEqual({m["path"] for m in item["matches"]},
                         {"manuscript/chapter-001.md", "world/moons.md"})
        self.assertEqual(item["scanned_files"] > 0, True)
        self.assertNotIn("TOP SECRET", json.dumps(item))
        self.assertEqual(storage.read_text(self.slug, "manuscript/chapter-001.md"), before)
        self.assertNotIn("Ada was born on Mars", before)

    def test_approval_and_human_review_are_required(self):
        item = self.new()
        with self.assertRaisesRegex(ValueError, "Approve"):
            update_ripple(self.slug, item["id"], action="mark_reviewed",
                          path="world/moons.md")
        with self.assertRaisesRegex(ValueError, "approved"):
            update_ripple(self.slug, item["id"], action="resolve")
        update_ripple(self.slug, item["id"], action="approve")
        with self.assertRaisesRegex(ValueError, "Review each"):
            update_ripple(self.slug, item["id"], action="resolve")
        update_ripple(self.slug, item["id"], action="mark_reviewed",
                      path="world/moons.md")
        update_ripple(self.slug, item["id"], action="mark_reviewed",
                      path="manuscript/chapter-001.md")
        resolved = update_ripple(self.slug, item["id"], action="resolve")
        self.assertEqual(resolved["status"], "resolved")
        self.assertEqual(list_ripples(self.slug)[0]["status"], "resolved")

    def test_rescan_preserves_human_reviews(self):
        item = self.new()
        update_ripple(self.slug, item["id"], action="approve")
        update_ripple(self.slug, item["id"], action="mark_reviewed",
                      path="world/moons.md")
        rescanned = update_ripple(self.slug, item["id"], action="rescan")
        statuses = {m["path"]: m["review_status"] for m in rescanned["matches"]}
        self.assertEqual(statuses["world/moons.md"], "reviewed")
        self.assertEqual(statuses["manuscript/chapter-001.md"], "pending")

    def test_invalid_source_and_short_facts_fail(self):
        with self.assertRaisesRegex(ValueError, "Source file"):
            find_impacts(self.slug, "Luna", "../other/manuscript/chapter-001.md")
        with self.assertRaisesRegex(ValueError, "between 3"):
            find_impacts(self.slug, "xy")
        with self.assertRaisesRegex(ValueError, "differ"):
            create_ripple(self.slug, title="Same", old_fact="The moon",
                          proposed_fact="the moon")

    def test_routes_only_expose_selected_project(self):
        client = TestClient(app)
        root = f"/api/projects/{self.slug}/canon-ripples"
        created = client.post(root, json={
            "title": "Birthplace", "old_fact": "Ada was born on Luna",
            "proposed_fact": "Ada was born on Mars", "source_path": "characters/captain.md"
        })
        self.assertEqual(created.status_code, 201, created.text)
        item = created.json()
        self.assertNotIn("TOP SECRET", created.text)
        self.assertEqual(len(client.get(root).json()), 1)
        self.assertEqual(client.get(f"/api/projects/{self.other['slug']}/canon-ripples").json(), [])
        self.assertEqual(client.get("/api/projects/missing/canon-ripples").status_code, 404)
        self.assertEqual(client.post(root + "/" + item["id"] + "/actions",
                          json={"action": "approve"}).status_code, 200)
        self.assertEqual(client.post(root + "/" + item["id"] + "/actions",
                          json={"action": "resolve"}).status_code, 400)
        self.assertEqual(client.post(root + "/bad-id/actions",
                          json={"action": "approve"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
