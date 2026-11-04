"""Author terminology and source-aware exception tests, fictional content only."""
import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage
from app.main import app
from app.style_bible import add, audit, decide, delete, rules


class StyleBibleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.addCleanup(gc.collect)
        fixture = patch.object(storage, "PROJECTS_ROOT", Path(temp.name) / "projects")
        fixture.start()
        self.addCleanup(fixture.stop)
        self.slug = storage.create_project("Synthetic Style Manuscript")["slug"]
        other = storage.create_project("Synthetic Private Project")["slug"]
        storage.save_text(other, "manuscript/secret.md", "DO_NOT_INCLUDE_PRIVATE_PROJECT")
        self.path = "manuscript/chapter-001.md"
        self.original = (
            "# First Signal\n\n"
            "Mira stepped into Aster Fall at sunrise. Aster Fall was strange. "
            "The lantern towers were very very bright. "
            "Suddenly, the road split in two. "
            "Mira crossed the square and saw aster fall written on an old banner.\n"
        )
        storage.save_text(self.slug, self.path, self.original)

    def test_preferred_spelling_and_boundary_matching(self):
        rule = add(self.slug, "preferred", "Aster Fall", "Asterfall", "Name of the capital.")
        result = audit(self.slug)
        found = [item for item in result["findings"] if item["rule_id"] == rule["id"]]
        self.assertEqual(len(found), 3)
        self.assertEqual({item["line"] for item in found}, {3})
        self.assertEqual(found[0]["preferred"], "Asterfall")
        self.assertEqual(found[0]["category"], "preferred")
        self.assertNotIn("DO_NOT_INCLUDE_PRIVATE_PROJECT", str(result))
        self.assertEqual(storage.read_text(self.slug, self.path), self.original)

    def test_avoid_watch_and_case_sensitive(self):
        add(self.slug, "avoid", "very very")
        add(self.slug, "watch", "Suddenly", case_sensitive=True)
        result = audit(self.slug)
        self.assertEqual(result["outstanding"], 2)
        self.assertEqual({r["category"] for r in result["findings"]}, {"avoid", "watch"})
        with self.assertRaisesRegex(ValueError, "already"):
            add(self.slug, "avoid", "very very")
        with self.assertRaisesRegex(ValueError, "differ"):
            add(self.slug, "preferred", "Mira", "mira")

    def test_dismissal_versioned_by_source_and_explicit_reason(self):
        rule = add(self.slug, "avoid", "very very")
        flagged = audit(self.slug)["findings"][0]
        with self.assertRaisesRegex(ValueError, "8"):
            decide(self.slug, flagged["id"], "dismiss", "ok")
        result = decide(self.slug, flagged["id"], "dismiss", "Dialogue is deliberately repetitive.")
        self.assertEqual(result["outstanding"], 0)
        self.assertEqual(result["dismissed"], 1)
        reopened = decide(self.slug, flagged["id"], "reopen")
        self.assertEqual(reopened["outstanding"], 1)
        decide(self.slug, flagged["id"], "dismiss", "Repetition is intentional here.")
        storage.save_text(self.slug, self.path, self.original + "\nThe author added another scene.")
        newer = audit(self.slug)
        self.assertEqual(newer["outstanding"], 1)
        with self.assertRaises(FileNotFoundError):
            decide(self.slug, flagged["id"], "dismiss", "Outdated source version")
        self.assertEqual(delete(self.slug, rule["id"])["deleted"], rule["id"])
        self.assertEqual(rules(self.slug), [])

    def test_api_project_scope(self):
        client = TestClient(app)
        root = f"/api/projects/{self.slug}/style-bible"
        self.assertEqual(client.get(root + "/audit").status_code, 200)
        self.assertEqual(client.get("/api/projects/nonexistent/style-bible/audit").status_code, 404)
        response = client.post(root + "/rules", json={
            "category": "preferred", "phrase": "Aster Fall", "preferred": "Asterfall"
        })
        self.assertEqual(response.status_code, 201, response.text)
        current = client.get(root + "/audit").json()
        self.assertEqual(current["outstanding"], 3)
        finding = current["findings"][0]
        decision = client.post(root + "/findings/" + finding["id"],
                               json={"action": "dismiss", "reason": "Banner inscription is historically accurate."})
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.json()["dismissed"], 1)
        self.assertEqual(client.delete(root + "/rules/" + response.json()["id"]).status_code, 200)
        self.assertEqual(client.get(root + "/rules").json(), [])


if __name__ == "__main__":
    unittest.main()
