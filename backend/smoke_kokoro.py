"""Manual, synthetic local neural voice smoke test. Never uses author manuscripts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.kokoro_local import _engine, model_paths, status


def main() -> None:
    import numpy as np
    import soundfile as sf

    info = status()
    if not info["installed"]:
        raise SystemExit("Local model or voices missing/incomplete")
    presets = [
        ("Narrator", "af_heart", "The lantern dimmed as the travelers reached the old gate."),
        ("Mira", "bf_emma", "I can hear something moving beyond the stone."),
        ("Captain", "am_adam", "Stay close. Nobody takes another step alone."),
    ]
    found = set(info["voice_ids"])
    for _, voice, _ in presets:
        if voice not in found:
            raise SystemExit(f"Model voice {voice} unavailable")
    model, voices = model_paths()
    kokoro = _engine(str(model), str(voices))
    chunks = []
    for name, voice, line in presets:
        audio, hz = kokoro.create(line, voice=voice, speed=1.0,
                                  lang="en-gb" if voice.startswith("b") else "en-us")
        if hz != 24000 or not len(audio):
            raise RuntimeError("Empty or bad sample rate in real inference for " + name)
        print(f"{name}: {voice} {len(audio)/hz:.2f}s", flush=True)
        chunks.extend([np.asarray(audio, np.float32), np.zeros(4800, np.float32)])
    output = Path.home() / "AppData" / "Local" / "EmberWriter" / "demos" / "three-voice-kokoro-test.wav"
    output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output, np.concatenate(chunks[:-1]), 24000, subtype="PCM_16")
    with sf.SoundFile(output) as track:
        details = {"path": str(output), "seconds": round(len(track) / track.samplerate, 2),
                   "samplerate": track.samplerate, "channels": track.channels,
                   "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
    print(json.dumps(details, indent=2), flush=True)


if __name__ == "__main__":
    main()
