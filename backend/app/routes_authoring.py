from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .binder import get_binder, sync_binder
from .ingest import SUPPORTED_UPLOADS, import_bytes, import_pasted_text
from .project_history import (
    compare_project_checkpoint,
    create_project_checkpoint,
    get_project_checkpoint,
    list_project_checkpoints,
    restore_project_checkpoint,
)
from .publishing import export_project
from .revisions import (
    compare_revisions,
    get_revision,
    list_revisions,
    record_revision,
    restore_revision,
)
from .storage import project_root, read_text

router = APIRouter(prefix="/api/projects/{slug}")
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


class PastedImportRequest(BaseModel):
    title: str = Field(default="Imported Text", max_length=160)
    content: str = Field(min_length=1, max_length=5_000_000)
    mode: Literal["novel", "portion", "idea", "research"] = "idea"


class CheckpointRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    note: str = Field(default="", max_length=1000)


class ProjectCheckpointRequest(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=2000)


class RestoreRequest(BaseModel):
    note: str = Field(default="", max_length=1000)


class PublishRequest(BaseModel):
    formats: list[Literal["docx", "epub", "pdf"]] = Field(min_length=1, max_length=3)
    title: str = Field(min_length=1, max_length=240)
    author: str = Field(default="", max_length=240)
    language: str = Field(default="en", min_length=2, max_length=20)
    include_toc: bool = True
    trim_width: float = Field(default=6.0, ge=4.0, le=8.5)
    trim_height: float = Field(default=9.0, ge=6.0, le=11.7)


UploadMode = Literal["novel", "portion", "idea", "research"]


@router.post("/import/files")
async def upload_files(
    slug: str,
    files: Annotated[list[UploadFile], File()],
    mode: Annotated[UploadMode, Form()] = "novel",
) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="Choose at least one file")
    results = []
    try:
        for upload in files:
            filename = upload.filename or "upload.txt"
            suffix = Path(filename).suffix.casefold()
            if suffix not in SUPPORTED_UPLOADS:
                raise ValueError(f"Unsupported upload type: {suffix or 'unknown'}")
            data = await upload.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise ValueError(f"{filename} exceeds the 100 MB upload limit")
            results.append(import_bytes(slug, filename, data, mode))
        binder = sync_binder(slug)
        return {
            "imports": results,
            "documents": sum(len(result["documents"]) for result in results),
            "words": sum(result["total_words"] for result in results),
            "binder": binder.model_dump(),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import/text")
def upload_text(slug: str, payload: PastedImportRequest) -> dict:
    try:
        result = import_pasted_text(slug, payload.title, payload.content, payload.mode)
        binder = sync_binder(slug)
        return {**result, "binder": binder.model_dump()}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/revisions")
def revisions(
    slug: str,
    path: str = Query(..., min_length=1),
    limit: int = Query(200, ge=1, le=1000),
) -> list[dict]:
    try:
        return list_revisions(slug, path, limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/revisions/checkpoint")
def checkpoint(slug: str, payload: CheckpointRequest) -> dict:
    try:
        content = read_text(slug, payload.path)
        return record_revision(
            slug,
            payload.path,
            content,
            source="checkpoint",
            note=payload.note,
            force=True,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/revisions/{revision_id}")
def revision(slug: str, revision_id: str) -> dict:
    try:
        return get_revision(slug, revision_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Revision not found") from exc


@router.get("/revisions/{revision_id}/diff")
def revision_diff(slug: str, revision_id: str, newer_id: str | None = None) -> dict:
    try:
        return compare_revisions(slug, revision_id, newer_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Revision not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/revisions/{revision_id}/restore")
def restore(slug: str, revision_id: str, payload: RestoreRequest) -> dict:
    try:
        return restore_revision(slug, revision_id, payload.note)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Revision not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/project-checkpoints")
def project_checkpoints(slug: str, limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    try:
        return list_project_checkpoints(slug, limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/project-checkpoints")
def create_full_checkpoint(slug: str, payload: ProjectCheckpointRequest) -> dict:
    try:
        return create_project_checkpoint(slug, payload.label, payload.note)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/project-checkpoints/{checkpoint_id}")
def project_checkpoint(slug: str, checkpoint_id: str) -> dict:
    try:
        return get_project_checkpoint(slug, checkpoint_id, include_content=False)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project checkpoint not found") from exc


@router.get("/project-checkpoints/{checkpoint_id}/compare")
def compare_full_checkpoint(slug: str, checkpoint_id: str) -> dict:
    try:
        return compare_project_checkpoint(slug, checkpoint_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project checkpoint not found") from exc


@router.post("/project-checkpoints/{checkpoint_id}/restore")
def restore_full_checkpoint(slug: str, checkpoint_id: str) -> dict:
    try:
        result = restore_project_checkpoint(slug, checkpoint_id)
        result["binder"] = get_binder(slug).model_dump()
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project checkpoint not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/publish")
def publish(slug: str, payload: PublishRequest) -> dict:
    try:
        return export_project(slug, **payload.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/exports/download")
def download_export(slug: str, path: str = Query(..., min_length=1)) -> FileResponse:
    root = project_root(slug)
    export_root = (root / "exports").resolve()
    candidate = (root / path).resolve()
    if export_root not in candidate.parents or not candidate.is_file():
        raise HTTPException(status_code=404, detail="Export not found")
    return FileResponse(candidate, filename=candidate.name, media_type="application/octet-stream")
