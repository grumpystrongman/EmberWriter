"""Part 3 source-linked manuscript health and author-approved paragraph revisions."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .developmental_editor import (
    apply_paragraph_changes,
    chapters_report,
    dialogue_report,
    document_report,
    restore_document_version,
)

router = APIRouter(prefix="/api/projects/{slug}/developmental-editor",
                   tags=["Developmental Editor"])


class ParagraphEdit(BaseModel):
    id: str = Field(pattern=r"^p[1-9][0-9]{0,5}$")
    replacement: str = Field(min_length=1, max_length=20_000)


class ApplyEdits(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    edits: list[ParagraphEdit] = Field(min_length=1, max_length=100)

class RestoreVersion(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    revision_id: str = Field(pattern=r"^[a-f0-9]{32}$")


def _fail(exc: Exception) -> None:
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=409 if "changed since review" in str(exc) else 400,
                        detail=str(exc)) from exc


@router.get("/overview")
def overview(slug: str, subjects: Annotated[list[str] | None, Query()] = None) -> dict:
    try:
        return chapters_report(slug, subjects or [])
    except (FileNotFoundError, OSError, ValueError) as exc:
        _fail(exc)


@router.get("/document")
def document(slug: str, path: str = Query(min_length=1)) -> dict:
    try:
        return document_report(slug, path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _fail(exc)


@router.get("/dialogue")
def dialogue(slug: str, path: str = Query(min_length=1)) -> dict:
    try:
        return dialogue_report(slug, path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _fail(exc)


@router.post("/apply")
def accept(slug: str, payload: ApplyEdits) -> dict:
    try:
        return apply_paragraph_changes(
            slug, payload.path, payload.source_hash, [edit.model_dump() for edit in payload.edits],
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        _fail(exc)


@router.post("/restore")
def restore(slug: str, payload: RestoreVersion) -> dict:
    try:
        return restore_document_version(
            slug, payload.path, payload.source_hash, payload.revision_id,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        _fail(exc)
