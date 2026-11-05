"""Private local audiobook rendering and chapter downloads."""
import asyncio
import subprocess

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .audiobook_local import (
    archive,
    audio_file,
    available_chapters,
    available_voices,
    list_renders,
    render,
)

router = APIRouter(prefix="/api/projects/{slug}/audiobook", tags=["Audiobook"])


class RenderRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    voice: str = Field(default="", max_length=120)
    rate: int = Field(default=-1, ge=-5, le=5)


@router.get("/chapters")
def chapters(slug: str) -> list[dict]:
    try:
        return available_chapters(slug)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc


@router.get("/voices")
def voices() -> dict:
    try:
        return {"engine": "windows-sapi-local", "voices": available_voices(),
                "privacy": "offline", "quality": "system voice; mastering is not included"}
    except (OSError, subprocess.SubprocessError) as exc:
        raise HTTPException(503, "Local Windows speech voices unavailable") from exc


@router.get("/renders")
def renders(slug: str) -> list[dict]:
    try:
        return list_renders(slug)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/renders")
async def create_render(slug: str, payload: RenderRequest) -> dict:
    try:
        from .local_resources import reservation
        async with reservation():
            return await asyncio.to_thread(render, slug, payload.path, payload.voice, payload.rate)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except NotImplementedError as exc:
        raise HTTPException(501, str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(400, str(exc)) from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(502, "Local audio engine failed or timed out") from exc


@router.get("/files/{filename}")
def download(slug: str, filename: str) -> FileResponse:
    try:
        path = audio_file(slug, filename)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return FileResponse(path, filename=path.name, media_type="audio/mpeg" if path.suffix == ".mp3" else "audio/wav")


@router.get("/export")
def download_archive(slug: str) -> FileResponse:
    try:
        path = archive(slug)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return FileResponse(path, filename="emberwriter-audiobook-chapters.zip", media_type="application/zip")


@router.get("/casting-text")
def casting_text(slug: str, path: str = Query(min_length=1, max_length=500)) -> dict:
    """Read-only spoken-text offsets for exact dialogue selection."""
    from .audiobook_local import _spoken_text
    from .storage import read_text
    try:
        sources = {item["path"] for item in available_chapters(slug)}
        if path not in sources:
            raise FileNotFoundError("Choose a manuscript chapter in this project")
        text = _spoken_text(read_text(slug, path))
        return {"path": path, "text": text}
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
