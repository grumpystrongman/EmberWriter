"""Recording-specific author proof-listening attestations.

Proof approval is not automated speech recognition: the author must confirm
full playback and line-by-line source alignment for the exact audio bytes.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from .audio_production import _write, load, synchronized
from .audiobook_local import audio_file, list_renders
from .audiobook_quality import _file_diagnostics
from .storage import read_text


def _digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def proof_status(slug: str, path: str, filename: str) -> dict:
    settings = load(slug)
    approval = settings.get("proof_approvals", {}).get(path)
    if not isinstance(approval, dict) or approval.get("filename") != filename:
        return {"approved": False, "reason": "No full-recording proof approval for this take"}
    try:
        recording = audio_file(slug, filename)
        source_hash = hashlib.sha256(read_text(slug, path).encode("utf-8")).hexdigest()
        if source_hash != approval.get("source_sha256"):
            return {"approved": False, "reason": "Manuscript changed after proof approval"}
        if _digest(recording) != approval.get("audio_sha256"):
            return {"approved": False, "reason": "Recording changed after proof approval"}
    except (OSError, ValueError, FileNotFoundError):
        return {"approved": False, "reason": "Approved source or recording is unavailable"}
    return {"approved": True, "approved_at": approval["approved_at"],
            "duration_seconds": approval["duration_seconds"], "source_aligned": True}


@synchronized
def approve(slug: str, path: str, listened_seconds: float,
            source_aligned: bool, full_listen: bool) -> dict:
    if not source_aligned or not full_listen:
        raise ValueError("Confirm a complete listen and line-by-line manuscript alignment")
    if isinstance(listened_seconds, bool) or not isinstance(listened_seconds, (float, int)):
        raise ValueError("Listened duration must be a number")
    track = next((row for row in list_renders(slug) if row["source_path"] == path), None)
    if track is None:
        raise ValueError("Narrate the manuscript chapter before approval")
    recording = audio_file(slug, track["filename"])
    details = _file_diagnostics(recording)
    duration = details.get("seconds")
    if details.get("valid") is not True or not duration or not (0.95 * duration <= listened_seconds <= 1.2 * duration):
        raise ValueError("Full recorded duration must be reviewed before approval")
    current_hash = hashlib.sha256(read_text(slug, path).encode("utf-8")).hexdigest()
    if track.get("source_hash") != current_hash:
        raise ValueError("Narration is stale; render the current manuscript first")
    settings = load(slug)
    if any(note.get("path") == path and note.get("filename") == track["filename"]
           and note.get("status") != "resolved" for note in settings["proof_notes"]):
        raise ValueError("Resolve all proof-listening notes for this recording")
    approval = {
        "filename": track["filename"], "source_sha256": current_hash,
        "audio_sha256": _digest(recording), "duration_seconds": duration,
        "listened_seconds": round(float(listened_seconds), 2),
        "source_aligned": True, "full_listen": True,
        "approved_at": datetime.now(UTC).isoformat(),
    }
    settings.setdefault("proof_approvals", {})[path] = approval
    _write(slug, settings)
    return approval


@synchronized
def revoke(slug: str, path: str) -> dict:
    settings = load(slug)
    if path not in settings.get("proof_approvals", {}):
        raise FileNotFoundError("No proof-listening approval exists for this chapter")
    del settings["proof_approvals"][path]
    return _write(slug, settings)
