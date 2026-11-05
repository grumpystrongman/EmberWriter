"""Dedicated, restart-recoverable offline M4B encode job endpoints."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import m4b_jobs
from .audiobook_local import _folder

router = APIRouter(prefix="/api/projects/{slug}/m4b-jobs", tags=["M4B Encoding"])


class EncodeRequest(BaseModel):
    mode: str = "original"


def _error(exc):
    raise HTTPException(404 if isinstance(exc, FileNotFoundError) else 409, str(exc)) from exc


@router.get("")
def get(slug: str) -> dict:
    try:
        return m4b_jobs.status(slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _error(exc)


@router.post("/start", status_code=202)
async def begin(slug: str, payload: EncodeRequest) -> dict:
    try:
        return m4b_jobs.start(slug, payload.mode)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _error(exc)


@router.post("/pause")
def pause(slug: str) -> dict:
    try:
        return m4b_jobs.pause(slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _error(exc)


@router.post("/resume", status_code=202)
async def resume(slug: str) -> dict:
    try:
        return m4b_jobs.resume(slug)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _error(exc)


@router.get("/download")
def download(slug: str) -> FileResponse:
    try:
        record = m4b_jobs.status(slug)
        if record["status"] != "completed":
            raise ValueError("Finish the current M4B encoding job before downloading")
        from .audiobook_quality import inspect
        if not inspect(slug)["ready"]:
            raise ValueError("Audiobook recordings changed after M4B encoding; verify and re-encode")
        filename = record["filename"]
        if filename not in ("current-book-narration.m4b", "current-book-narration-leveled.m4b"):
            raise ValueError("Invalid M4B artifact name")
        file = _folder(slug) / filename
        if not file.is_file():
            raise FileNotFoundError("Encoded M4B is missing")
        from .m4b_jobs import _identity
        from .audiobook_jobs import _hash_audio_file
        if not record.get("input_identity") or _identity(slug) != record["input_identity"]:
            raise ValueError("Audiobook inputs changed after encoding; re-encode the current audio")
        if not record.get("artifact_sha256") or _hash_audio_file(file) != record["artifact_sha256"]:
            raise ValueError("Encoded M4B file changed since verification")
        return FileResponse(file, filename="emberwriter-" + ("leveled-" if record["mode"] == "leveled" else "") + "audiobook.m4b",
                            media_type="audio/mp4")
    except (FileNotFoundError, ValueError, OSError) as exc:
        _error(exc)
