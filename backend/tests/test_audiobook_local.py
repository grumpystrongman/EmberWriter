"""Offline audiobook smoke and filesystem isolation checks (synthetic content)."""
from __future__ import annotations

import gc
import io
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage
from app.audiobook_local import _spoken_text, archive, audio_file, available_chapters, list_renders, render
from app.main import app


class AudiobookLocalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(gc.collect)
        fixture = patch.object(storage, "PROJECTS_ROOT", Path(self.temp.name) / "projects")
        fixture.start()
        self.addCleanup(fixture.stop)
        self.slug = storage.create_project("Synthetic Audiobook")["slug"]
        other = storage.create_project("Private Novel Untouched")["slug"]
        storage.save_text(other, "manuscript/private.md", "DO_NOT_SHARE_ME")
        storage.save_text(self.slug, "manuscript/chapter-001.md",
                          "# Chapter One\n\nThe skyship glided above the harbor. "
                          "Its crew watched the stars wake across the sky.\n")
        self.other = other

    def test_chapter_listing_and_speech_cleanup(self):
        chapters = available_chapters(self.slug)
        self.assertTrue(any(ch["path"] == "manuscript/chapter-001.md" for ch in chapters))
        self.assertNotIn("private", str(chapters).lower())
        self.assertEqual(_spoken_text("## Hello\n\n**Story** [link](https://example.com)"),
                         "Hello\n\nStory link")

    def test_render_and_archive_offline_with_synthetic_voice(self):
        def fake_sapi(cmd, **kwargs):
            dest = Path(cmd[cmd.index("-OutputPath") + 1])
            with wave.open(str(dest), "wb") as writer:
                writer.setnchannels(1)
                writer.setsampwidth(2)
                writer.setframerate(16000)
                writer.writeframes(b"\x00\x00" * 1000)
            return None

        with patch("app.audiobook_local.subprocess.run", side_effect=fake_sapi), patch("app.audiobook_local.shutil.which", return_value=None):
            track = render(self.slug, "manuscript/chapter-001.md")
        self.assertEqual(track["filename"][-4:], ".wav")
        self.assertTrue(audio_file(self.slug, track["filename"]).exists())
        self.assertEqual(len(list_renders(self.slug)), 1)
        zip_path = archive(self.slug)
        with zipfile.ZipFile(zip_path) as z:
            self.assertIn(track["filename"], z.namelist())
            self.assertIn("manifest.json", z.namelist())
            self.assertNotIn("DO_NOT_SHARE_ME", z.read("manifest.json").decode("utf-8"))
        with self.assertRaisesRegex(ValueError, "Invalid"):
            audio_file(self.slug, "../secret.txt")

    def test_api_is_project_scoped(self):
        client = TestClient(app)
        url = f"/api/projects/{self.slug}/audiobook"
        response = client.get(url + "/chapters")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(client.get(f"/api/projects/{self.other}/audiobook/renders").json(), [])
        self.assertEqual(client.get(url + "/files/..%2Fsecret.txt").status_code, 404)
        response = client.post(url + "/renders", json={"path": "../private.md", "voice": ""})
        self.assertEqual(response.status_code, 400, response.text)


if __name__ == "__main__":
    unittest.main()
