"""Public API for Series Vault, Canon Graph and temporal questions.

All mutations require explicit author actions and operate on locally stored,
rights-confirmed series sources; no AI text ingestion or automatic canon changes.
"""
from __future__ import annotations

from typing import Annotated

import sqlite3

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from . import series_canon as canon
from . import series_vault as vault

router = APIRouter(prefix="/api/series", tags=["Series Vault"])


class SeriesCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)


class AttachProject(BaseModel):
    project_slug: str = Field(min_length=1, max_length=120)
    ordinal: int = Field(ge=1, le=9999)
    title: str | None = Field(default=None, max_length=180)
    kind: str = "novel"
    edition_status: str = "draft"
    rights_confirmed: bool = False


class VolumeEdit(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    ordinal: int = Field(ge=1, le=9999)
    kind: str
    edition_status: str


class EntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = "character"
    aliases: list[str] = Field(default_factory=list, max_length=30)
    description: str = Field(default="", max_length=3000)


class EntityEdit(BaseModel):
    aliases: list[str] = Field(default_factory=list, max_length=30)
    description: str = Field(default="", max_length=3000)


class FactCreate(BaseModel):
    subject_id: str
    predicate: str = Field(min_length=1, max_length=60)
    object_text: str = Field(default="", max_length=500)
    object_entity_id: str | None = None
    scope: str = "world"
    knower_id: str | None = None
    start_book: int = Field(ge=1, le=9999)
    start_sequence: int = Field(default=0, ge=0, le=999999)
    end_book: int | None = Field(default=None, ge=1, le=9999)
    end_sequence: int | None = Field(default=None, ge=0, le=999999)
    source_id: str
    quote_start: int = Field(ge=0)
    quote_end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=2000)
    note: str = Field(default="", max_length=1200)


class Review(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")


class TemporalQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=1500)
    book: int = Field(ge=1, le=9999)
    sequence: int = Field(default=999999, ge=0, le=999999)
    scope: str = "world"
    knower_id: str | None = None
    subject_id: str | None = None


def _fail(exc: Exception):
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(404, str(exc)) from exc
    if isinstance(exc, sqlite3.IntegrityError):
        raise HTTPException(409, "A book order or series name is already in use") from exc
    raise HTTPException(400, str(exc)) from exc


@router.get("")
def list_all_series() -> list[dict]:
    return vault.list_series()


@router.post("", status_code=201)
def new_series(payload: SeriesCreate) -> dict:
    try:
        return vault.create_series(payload.title, payload.description)
    except (ValueError, OSError) as exc:
        _fail(exc)


@router.get("/{series_id}")
def inspect_series(series_id: str) -> dict:
    try:
        return vault.series_detail(series_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/volumes/project", status_code=201)
def add_existing_project(series_id: str, payload: AttachProject) -> dict:
    try:
        return vault.attach_project(
            series_id, payload.project_slug, payload.ordinal,
            title=payload.title, kind=payload.kind,
            edition_status=payload.edition_status,
            rights_confirmed=payload.rights_confirmed,
        )
    except (ValueError, FileNotFoundError, sqlite3.IntegrityError) as exc:
        _fail(exc)


@router.put("/{series_id}/volumes/{volume_id}")
def edit_volume(series_id: str, volume_id: str, payload: VolumeEdit) -> dict:
    try:
        return vault.update_volume(series_id, volume_id, **payload.model_dump())
    except (ValueError, FileNotFoundError, sqlite3.IntegrityError) as exc:
        _fail(exc)


@router.post("/{series_id}/volumes/import", status_code=201)
async def import_document(
    series_id: str,
    file: Annotated[UploadFile, File()],
    ordinal: int = Form(...),
    title: str = Form(default=""),
    kind: str = Form(default="novel"),
    edition_status: str = Form(default="draft"),
    rights_confirmed: bool = Form(default=False),
) -> dict:
    try:
        if not rights_confirmed:
            raise ValueError("Confirm ownership or import permission first")
        name = file.filename or ""
        if not name or len(name) > 250:
            raise ValueError("A supported manuscript filename is required")
        # Read at most the size limit + 1 so a hostile upload cannot grow memory.
        blob = await file.read(vault.MAX_IMPORT_BYTES + 1)
        if len(blob) > vault.MAX_IMPORT_BYTES:
            raise ValueError("File exceeds the 25 MB local import limit")
        return vault.import_volume(
            series_id, name, blob, ordinal, title=title or None, kind=kind,
            edition_status=edition_status, rights_confirmed=rights_confirmed,
        )
    except (ValueError, FileNotFoundError, sqlite3.IntegrityError, UnicodeError) as exc:
        _fail(exc)


@router.get("/{series_id}/volumes/{volume_id}/sources")
def list_volume_sources(series_id: str, volume_id: str) -> list[dict]:
    try:
        return vault.volume_sources(series_id, volume_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/sources/{source_id}/excerpt")
def show_source(
    series_id: str, source_id: str, query: str = Query(default="", max_length=400),
    limit: int = Query(default=1200, ge=120, le=5000),
) -> dict:
    try:
        return vault.list_source_excerpt(series_id, source_id, query, limit)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/entities")
def all_entities(series_id: str) -> list[dict]:
    try:
        return canon.list_entities(series_id)
    except FileNotFoundError as exc:
        _fail(exc)


@router.post("/{series_id}/entities", status_code=201)
def new_entity(series_id: str, payload: EntityCreate) -> dict:
    try:
        return canon.add_entity(series_id, payload.name, payload.kind,
                                aliases=payload.aliases, description=payload.description)
    except (ValueError, FileNotFoundError, sqlite3.IntegrityError) as exc:
        _fail(exc)


@router.put("/{series_id}/entities/{entity_id}")
def update_entity(series_id: str, entity_id: str, payload: EntityEdit) -> dict:
    try:
        return canon.edit_entity(series_id, entity_id,
                                 aliases=payload.aliases, description=payload.description)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/assertions")
def assertions(series_id: str, status: str | None = None,
               subject_id: str | None = None) -> list[dict]:
    try:
        return canon.list_facts(series_id, status=status, subject_id=subject_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/assertions", status_code=201)
def new_assertion(series_id: str, payload: FactCreate) -> dict:
    try:
        return canon.propose_fact(series_id, **payload.model_dump())
    except (ValueError, FileNotFoundError, sqlite3.IntegrityError) as exc:
        _fail(exc)


@router.post("/{series_id}/assertions/{fact_id}/review")
def review_assertion(series_id: str, fact_id: str, payload: Review) -> dict:
    try:
        return canon.review_fact(series_id, fact_id, payload.decision)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/at")
def state_at(series_id: str, book: int = Query(ge=1, le=9999),
             sequence: int = Query(default=999999, ge=0, le=999999),
             scope: str = "world", subject_id: str | None = None,
             knower_id: str | None = None) -> dict:
    try:
        return canon.at_book(series_id, book, sequence, scope=scope,
                             subject_id=subject_id, knower_id=knower_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/timeline")
def series_timeline(series_id: str, subject_id: str | None = None) -> dict:
    try:
        return canon.timeline(series_id, subject_id=subject_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/ask")
def temporal_answer(series_id: str, payload: TemporalQuestion) -> dict:
    try:
        return canon.ask_temporal(
            series_id, payload.question, payload.book,
            sequence=payload.sequence, scope=payload.scope,
            knower_id=payload.knower_id, subject_id=payload.subject_id,
        )
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)
