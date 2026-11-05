"""Audiobook direction, local lexicon and proof notes using synthetic stories only."""
from __future__ import annotations

import asyncio
import gc
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage, audiobook_jobs, audiobook_local, audio_production
from app.audiobook_quality import inspect
from app.binder import sync_binder
from app.main import app


class AudioDirectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fixture = patch.object(storage, "PROJECTS_ROOT", Path(self.tmp.name) / "projects")
        self.fixture.start()
        self.slug = storage.create_project("Synthetic Glossary Starship")["slug"]
        other = storage.create_project("Synthetic Separated Project")["slug"]
        storage.save_text(other, "manuscript/secret.md", "OTHER_PROJECT_SECRET_DO_NOT_USE")
        self.path = "manuscript/chapter-001.md"
        storage.save_text(self.slug, self.path, "# First Light\n\n" + "The traveler crossed Aster Vale with Mira. " * 35)
        sync_binder(self.slug)
        self.commands = []

    async def asyncTearDown(self):
        await audiobook_jobs.stop_on_shutdown()
        self.fixture.stop()
        gc.collect()
        self.tmp.cleanup()

    def fake_sapi(self, args, **kwargs):
        if "-OutputPath" not in args:
            return None
        self.commands.append(args)
        source = Path(args[args.index("-InputPath") + 1])
        self.assertIn("AS-ter VAYL", source.read_text(encoding="utf-8"))
        self.assertNotIn("OTHER_PROJECT_SECRET", source.read_text(encoding="utf-8"))
        wav = Path(args[args.index("-OutputPath") + 1])
        with wave.open(str(wav), "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(2)
            writer.setframerate(16000)
            writer.writeframes(b"\x02\x00" * 16000)

    async def wait_done(self):
        for _ in range(400):
            job = audiobook_jobs.status(self.slug)
            if job["status"] in ("completed", "needs_attention") and not job["active"]:
                return job
            await asyncio.sleep(.012)
        self.fail("No finished synthetic narration job")

    async def test_lexicon_profile_and_proof_notes_block_stale_audio(self):
        audio_production.save_pronunciation(self.slug, "Aster Vale", "AS-ter VAYL")
        with patch("app.audiobook_local.available_voices", return_value=["Synthetic Narrator"]):
            audio_production.save_profile(self.slug, self.path, "Synthetic Narrator", 3)
        self.assertEqual(audio_production.spoken_replacements(
            "AstER vale and Aster Vale! Unaster Vale.",
            audio_production.load(self.slug)["pronunciations"]),
            "AS-ter VAYL and AS-ter VAYL! Unaster Vale.")
        with patch("app.audiobook_local.subprocess.run", side_effect=self.fake_sapi), patch(
            "app.audiobook_local.shutil.which", return_value=None
        ), patch("app.audiobook_local.available_voices", return_value=["Synthetic Narrator"]):
            job = audiobook_jobs.start(self.slug, voice="", rate=-1)
            self.assertTrue(job["settings_signature"])
            self.assertEqual((state := await self.wait_done())["status"], "completed", state["message"])
        self.assertEqual(self.commands[0][self.commands[0].index("-Voice") + 1], "Synthetic Narrator")
        self.assertEqual(self.commands[0][self.commands[0].index("-Rate") + 1], "3")
        self.assertFalse(inspect(self.slug)["ready"])
        self.assertIn("proof-listening not approved", str(inspect(self.slug)["issues"]))
        from app.proof_approval import approve
        approve(self.slug, self.path, 1.0, True, True)
        self.assertTrue(inspect(self.slug)["ready"])
        self.assertTrue(audiobook_local.archive(self.slug).exists())
        self.assertTrue(audiobook_jobs.batch_archive(self.slug).exists())
        note = audio_production.add_note(self.slug, self.path, 12.5, "Fix the fictional place name")
        self.assertFalse(inspect(self.slug)["ready"])
        self.assertIn("proof-listening", str(inspect(self.slug)["issues"]))
        with self.assertRaisesRegex(ValueError, "unresolved proof-listening"):
            audiobook_jobs.batch_archive(self.slug)
        audio_production.resolve_note(self.slug, note["id"], True)
        self.assertTrue(inspect(self.slug)["ready"])
        audio_production.save_pronunciation(self.slug, "Mira", "MEE-rah")
        self.assertFalse(inspect(self.slug)["ready"])
        self.assertIn("changed", str(inspect(self.slug)["issues"]))
        with self.assertRaisesRegex(ValueError, "settings changed|dictionary"):
            audiobook_jobs.batch_archive(self.slug)
        with self.assertRaisesRegex(ValueError, "dictionary"):
            audiobook_local.archive(self.slug)
        with self.assertRaisesRegex(ValueError, "readiness"):
            from app.audiobook_m4b import export_m4b
            with patch("app.audiobook_m4b.shutil.which", return_value="ffmpeg"):
                export_m4b(self.slug)
        self.assertNotIn("OTHER_PROJECT_SECRET", str(audio_production.load(self.slug)))

    async def test_api_validation_and_isolation(self):
        client = TestClient(app)
        base = f"/api/projects/{self.slug}/audiobook-production"
        self.assertEqual(client.get(base).status_code, 200)
        self.assertEqual(client.get("/api/projects/missing/audiobook-production").status_code, 404)
        self.assertEqual(client.put(base + "/pronunciations", json={
            "written": "Aster Vale", "spoken": "AS-ter VAYL",
        }).status_code, 200)
        self.assertEqual(client.put(base + "/pronunciations", json={
            "written": "bad", "spoken": "<speak>no markup</speak>",
        }).status_code, 409)
        self.assertEqual(client.put(base + "/profiles", json={
            "path": "../other.md", "voice": "", "rate": 0,
        }).status_code, 404)
        self.assertEqual(client.post(base + "/notes", json={
            "path": self.path, "seconds": 5, "note": "Listen again",
        }).status_code, 409)
        self.assertEqual(client.delete(base + "/pronunciations/Aster%20Vale").status_code, 200)
        self.assertEqual(audio_production.load(self.slug)["pronunciations"], [])

    async def test_batch_freezes_dictionary_at_start(self):
        audio_production.save_pronunciation(self.slug, "Aster Vale", "AS-ter VAYL")
        started = asyncio.Event()
        release = asyncio.Event()
        loop = asyncio.get_running_loop()
        def blocking_render(*args, **kwargs):
            loop.call_soon_threadsafe(started.set)
            import time
            while not release.is_set():
                time.sleep(.005)
            return {"filename": "0000000000000001.wav"}
        with patch("app.audiobook_jobs.render", side_effect=blocking_render):
            audiobook_jobs.start(self.slug)
            await asyncio.wait_for(started.wait(), 2)
            audio_production.save_pronunciation(self.slug, "Aster Vale", "NEW SOUND")
            release.set()
            state = await self.wait_done()
        self.assertEqual(state["status"], "needs_attention")
        self.assertIn("settings changed", state["message"].lower())


if __name__ == "__main__":
    unittest.main()
