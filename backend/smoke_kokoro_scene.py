"""Optional real end-to-end test of author's scene rehearsal over FastAPI."""
from __future__ import annotations

import hashlib
import json
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import audio_production, storage
from app.main import app


def main() -> None:
    text = ('At the abandoned observatory, the candles flickered. '
            '"Someone has been here before us," said Mira. '
            'A low rumble moved through the stone. '
            '"Then we do not go in alone," the captain replied. '
            'The wind answered with a long, uncertain howl.')
    casts = [
        ('"Someone has been here before us,"', "Mira"),
        ('"Then we do not go in alone,"', "Captain"),
    ]
    with tempfile.TemporaryDirectory() as temporary, patch.object(
        storage, "PROJECTS_ROOT", Path(temporary) / "projects"
    ):
        slug = storage.create_project("Real Neural Rehearsal Verification")["slug"]
        path = "manuscript/demo.md"
        storage.save_text(slug, path, text)
        audio_production.save_character_voice(slug, "Mira", "")
        audio_production.save_character_voice(slug, "Captain", "")
        with TestClient(app) as client:
            health = client.get(f"/api/projects/{slug}/audiobook-production/kokoro/status")
            assert health.status_code == 200, health.text
            assert health.json()["installed"], health.text
            for character, voice in [
                ("Narrator", "af_heart"), ("Mira", "bf_emma"), ("Captain", "am_adam")
            ]:
                response = client.put(
                    f"/api/projects/{slug}/audiobook-production/kokoro/voices",
                    json={"character": character, "voice_id": voice, "speed": 1.0},
                )
                assert response.status_code == 200, response.text
            for quote, character in casts:
                start = text.index(quote)
                result = client.put(
                    f"/api/projects/{slug}/audiobook-production/casting",
                    json={"path": path, "start": start, "end": start + len(quote),
                          "text": quote, "voice": "", "character": character},
                )
                assert result.status_code == 200, result.text
            body = {"path": path, "start": 0, "end": len(text)}
            plan = client.post(f"/api/projects/{slug}/audiobook-production/kokoro/scene-plan",
                               json=body)
            assert plan.status_code == 200, plan.text
            assert [part["speaker"] for part in plan.json()["segments"]] == [
                "Narrator", "Mira", "Narrator", "Captain", "Narrator"
            ]
            response = client.post(
                f"/api/projects/{slug}/audiobook-production/kokoro/rehearsals", json=body
            )
            assert response.status_code == 200, response.text
            details = response.json()
            assert details["status"] == "unapproved_rehearsal"
            download = client.get(
                f"/api/projects/{slug}/audiobook-production/kokoro/rehearsals/"
                + details["filename"]
            )
            assert download.status_code == 200
            target = Path.home() / "AppData" / "Local" / "EmberWriter" / "demos" / "author-scene-three-voices.wav"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(download.content)
            with wave.open(str(target), "rb") as wav:
                assert wav.getframerate() == 24000 and wav.getnframes() > 24000
                duration = wav.getnframes() / wav.getframerate()
            print(json.dumps({
                "path": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "duration_seconds": round(duration, 2),
                "speakers": [s["speaker"] for s in details["segments"]],
                "status": details["status"],
                "source_sha256": details["source_sha256"],
            }, indent=2), flush=True)


if __name__ == "__main__":
    main()
