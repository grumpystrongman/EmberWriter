"""Real local two-chapter neural book smoke; synthetic fiction only."""
import hashlib
import json
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import audio_production, storage
from app.main import app


def main():
    with tempfile.TemporaryDirectory() as base, patch.object(
        storage, "PROJECTS_ROOT", Path(base) / "projects"
    ):
        slug = storage.create_project("Synthetic Two-Chapter Neural Book")["slug"]
        chapters = [
            ("manuscript/chapter-1.md", 'The lantern dimmed at the edge of the forest. Mira said, "Keep your light close." The trail curved around a broken tower.'),
            ("manuscript/chapter-2.md", 'The captain stood beside the ancient doorway. The wind whispered through the stones. At last the travelers stepped into the hall.'),
        ]
        for name, chapter in chapters:
            storage.save_text(slug, name, chapter)
        audio_production.save_character_voice(slug, "Mira", "")
        doc = [{"path": name, "title": "Chapter " + str(i + 1), "content": chapter}
               for i, (name, chapter) in enumerate(chapters)]
        with TestClient(app) as client:
            base_url = f"/api/projects/{slug}/audiobook-production"
            for name, preset in (("Narrator", "af_heart"), ("Mira", "bf_emma")):
                response = client.put(base_url + "/kokoro/voices", json={
                    "character": name, "voice_id": preset, "speed": 1.0,
                })
                assert response.status_code == 200, response.text
            first = chapters[0][1]
            phrase = '"Keep your light close."'
            start = first.index(phrase)
            cast = client.put(base_url + "/casting", json={
                "path": chapters[0][0], "start": start, "end": start + len(phrase),
                "text": phrase, "voice": "", "character": "Mira",
            })
            assert cast.status_code == 200, cast.text
            with patch("app.kokoro_book.compiled_documents", return_value=doc):
                result = client.post(base_url + "/kokoro/book")
                assert result.status_code == 200, result.text
                job = result.json()
                steps = 0
                while job["status"] != "completed":
                    result = client.post(base_url + "/kokoro/book/next")
                    assert result.status_code == 200, result.text
                    job = result.json()
                    steps += 1
                    print(f"Rendered {job['completed']}/{job['total']} chunks", flush=True)
                assert steps == job["total"]
                assert not job["publication_approved"]
                outputs = []
                for i, row in enumerate(job["chapters"], 1):
                    assert row["status"] == "rendered_unapproved"
                    wave_data = client.get(base_url + "/kokoro/book/audio/" + row["filename"])
                    assert wave_data.status_code == 200
                    final_dir = Path.home() / "AppData" / "Local" / "EmberWriter" / "demos"
                    final_dir.mkdir(parents=True, exist_ok=True)
                    final = final_dir / f"neural-book-chapter-{i}.wav"
                    final.write_bytes(wave_data.content)
                    with wave.open(str(final), "rb") as audio:
                        duration = audio.getnframes() / audio.getframerate()
                        assert duration > 1
                    outputs.append({
                        "filename": str(final), "duration": round(duration, 2),
                        "sha256": hashlib.sha256(wave_data.content).hexdigest(),
                    })
                print(json.dumps({"status": job["status"], "chunks": steps,
                                  "chapters": outputs, "approved": False}, indent=2), flush=True)


if __name__ == "__main__":
    main()
