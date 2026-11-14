"""Public API for Series Vault, Canon Graph and temporal questions.

All mutations require explicit author actions and operate on locally stored,
rights-confirmed series sources; no AI text ingestion or automatic canon changes.
"""
from __future__ import annotations

import sqlite3
from typing import Annotated

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import series_bulk_import, series_epub_index, series_epub_structure
from . import series_canon as canon
from . import series_discovery as discovery
from . import series_evidence_search as evidence_search
from . import series_extraction_jobs as extraction_jobs
from . import series_knowledge_lab as knowledge_lab
from . import series_scene_preflight as scene_preflight
from . import series_scene_studio as scene_studio
from . import series_story_state as intelligence
from . import series_vault as vault
from . import story_benchmark_jobs as benchmarks

router = APIRouter(prefix="/api/series", tags=["Series Vault"])


class SeriesCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)


class ModelProbeCreate(BaseModel):
    model: str = Field(min_length=1, max_length=200)


class ModelEvaluationCreate(BaseModel):
    model: str = Field(min_length=1, max_length=200)


class SeriesDelete(BaseModel):
    confirmation: str = Field(min_length=1, max_length=160)


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


class ExtractionStart(BaseModel):
    source_id: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)


class SourceSuggestion(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class SceneBoardPayload(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    book: int = Field(ge=1, le=9999)
    sequence: int = Field(default=0, ge=0, le=999999)
    objective: str = Field(default='', max_length=1200)
    conflict: str = Field(default='', max_length=1200)
    opening: str = Field(default='', max_length=1600)
    aftermath: str = Field(default='', max_length=1600)
    voice_notes: str = Field(default='', max_length=1200)
    pov_id: str | None = None
    location_id: str | None = None
    participants: list[str] = Field(default_factory=list, max_length=20)
    beats: list[dict] = Field(min_length=1, max_length=24)


class SceneBoardUpdate(SceneBoardPayload):
    version: int = Field(ge=1)


class SceneBoardDelete(BaseModel):
    version: int = Field(ge=1)


class SceneClaim(BaseModel):
    subject_id: str
    predicate: str = Field(min_length=1, max_length=60)
    object_text: str = Field(default="", max_length=500)
    object_entity_id: str | None = None
    scope: str = "world"
    knower_id: str | None = None


class SceneCheck(BaseModel):
    scene: str = Field(min_length=1, max_length=35000)
    book: int = Field(ge=1, le=9999)
    sequence: int = Field(default=999999, ge=0, le=999999)
    assertions: list[SceneClaim] = Field(default_factory=list, max_length=100)


class ContinuityException(BaseModel):
    claim_key: str = Field(min_length=64, max_length=64)
    reason: str = Field(min_length=1, max_length=80)
    note: str = Field(min_length=1, max_length=1000)


class ConsequencePreview(BaseModel):
    subject_id: str
    predicate: str = Field(min_length=1, max_length=60)
    proposed_value: str = Field(min_length=1, max_length=500)
    effective_book: int = Field(ge=1, le=9999)
    scope: str = "world"
    include_past: bool = False


class ConsequenceSave(ConsequencePreview):
    proposal_id: str = Field(min_length=64, max_length=64)
    note: str = Field(min_length=1, max_length=1500)


class EmberSeriesQuestion(BaseModel):
    question: str = Field(min_length=3, max_length=1500)
    book: int = Field(default=0, ge=0, le=9999)
    sequence: int = Field(default=999999, ge=0, le=999999)
    scope: str = "world"
    knower_id: str | None = None
    subject_id: str | None = None
    use_local_model: bool = False
    allow_sources: bool = False
    model: str = Field(default="", max_length=200)


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


@router.post("/restore", status_code=201)
async def restore_vault(
    file: Annotated[UploadFile, File()],
    rights_confirmed: bool = Form(default=False),
) -> dict:
    from .series_portability import MAX_ARCHIVE_BYTES, restore
    try:
        if not rights_confirmed:
            raise ValueError("Confirm that you are authorized to restore these books")
        data = await file.read(MAX_ARCHIVE_BYTES + 1)
        if len(data) > MAX_ARCHIVE_BYTES:
            raise ValueError("Series archive exceeds the 250 MB upload limit")
        return restore(data, rights_confirmed)
    except (ValueError, OSError, sqlite3.IntegrityError) as exc:
        _fail(exc)


@router.get("/{series_id}/discover")
def discover_evidence(series_id: str, book: int | None = Query(default=None, ge=1, le=9999),
                      limit: int = Query(default=120, ge=1, le=250),
                      offset: int = Query(default=0, ge=0)) -> dict:
    """Read-only whole-source literal evidence candidates for deliberate author review."""
    try:
        return discovery.discover(series_id, book=book, limit=limit, offset=offset)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/model-evaluation")
def model_evaluation_status(series_id: str) -> dict:
    try:
        return benchmarks.status(series_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/model-evaluation", status_code=202)
def start_model_evaluation(series_id: str, payload: ModelEvaluationCreate,
                           background_tasks: BackgroundTasks) -> dict:
    try:
        job = benchmarks.queue(series_id, payload.model)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)
    background_tasks.add_task(benchmarks.execute, series_id, payload.model)
    return job


@router.post("/{series_id}/scene-preflight")
def preview_scene_staging(series_id: str, payload: SceneBoardPayload) -> dict:
    try:
        return scene_preflight.preflight(series_id, payload.model_dump())
    except (FileNotFoundError, ValueError) as exc:
        _fail(exc)


@router.get("/{series_id}/scene-boards")
def get_scene_boards(series_id: str, book: int | None = Query(default=None, ge=1)) -> list[dict]:
    try:
        return scene_studio.list_boards(series_id, book)
    except (FileNotFoundError, ValueError) as exc:
        _fail(exc)


@router.post("/{series_id}/scene-boards", status_code=201)
def create_scene_board(series_id: str, payload: SceneBoardPayload) -> dict:
    try:
        return scene_studio.create_board(series_id, payload.model_dump())
    except (FileNotFoundError, ValueError) as exc:
        _fail(exc)


@router.put("/{series_id}/scene-boards/{board_id}")
def update_scene_board(series_id: str, board_id: str, payload: SceneBoardUpdate) -> dict:
    try:
        return scene_studio.update_board(series_id, board_id, payload.version, payload.model_dump(exclude={"version"}))
    except (FileNotFoundError, ValueError) as exc:
        _fail(exc)


@router.post("/{series_id}/scene-boards/{board_id}/delete")
def remove_scene_board(series_id: str, board_id: str, payload: SceneBoardDelete) -> dict:
    try:
        return scene_studio.delete_board(series_id, board_id, payload.version)
    except (FileNotFoundError, ValueError) as exc:
        _fail(exc)


@router.post("/{series_id}/local-model-probe")
async def test_private_local_model(series_id: str, payload: ModelProbeCreate) -> dict:
    """Only a synthetic sentence is submitted to local inference."""
    from .series_model_probe import probe
    try:
        return await probe(series_id, payload.model)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/local-model-stream-probe")
async def test_private_streaming_model(
    series_id: str, payload: ModelProbeCreate, request: Request,
) -> dict:
    """Bounded, cancellable, synthetic-only streaming inference diagnostic."""
    from .series_model_stream_probe import probe
    try:
        return await probe(series_id, payload.model, is_disconnected=request.is_disconnected)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/local-model-readiness")
def private_local_model_readiness(series_id: str) -> dict:
    """Service-only health check; never transmits story text."""
    from .series_model_readiness import model_readiness
    try:
        return model_readiness(series_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/knowledge-lab")
def source_grounded_knowledge(
    series_id: str,
    book: int = Query(ge=1, le=9999),
    sequence: int = Query(default=999999, ge=0, le=999999),
    subject_id: str | None = None,
    other_id: str | None = None,
    knower_id: str | None = None,
) -> dict:
    """Only author-approved, temporal, cited evidence; never model guesses."""
    try:
        return knowledge_lab.investigate(
            series_id, book, sequence=sequence, subject_id=subject_id,
            other_id=other_id, knower_id=knower_id,
        )
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/story-state")
def unified_story_state(series_id: str, book: int = Query(ge=1, le=9999),
                        sequence: int = Query(default=999999, ge=0, le=999999)) -> dict:
    """Read-only, author-approved, spoiler-aware story-state projection."""
    try:
        return intelligence.story_state(series_id, book, sequence)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/backup")
def download_vault(series_id: str, background_tasks: BackgroundTasks) -> FileResponse:
    from .series_portability import backup
    try:
        archive = backup(series_id)
    except (FileNotFoundError, OSError, ValueError) as exc:
        _fail(exc)
    background_tasks.add_task(archive.unlink, missing_ok=True)
    return FileResponse(
        archive, filename="emberwriter-series-backup.zip",
        media_type="application/zip", background=background_tasks,
    )


@router.post("/{series_id}/delete")
def remove_series(series_id: str, payload: SeriesDelete) -> dict:
    try:
        return vault.delete_series(series_id, payload.confirmation)
    except (ValueError, FileNotFoundError, sqlite3.IntegrityError) as exc:
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


@router.post("/{series_id}/volumes/bulk-zip", status_code=201)
async def import_epub_collection(
    series_id: str,
    file: Annotated[UploadFile, File()],
    rights_confirmed: bool = Form(default=False),
) -> dict:
    """Safely add all numbered EPUBs in one local ZIP, in series order."""
    try:
        blob = await file.read(series_bulk_import.MAX_ARCHIVE_BYTES + 1)
        return series_bulk_import.import_epub_zip(
            series_id, blob, rights_confirmed=rights_confirmed,
        )
    except (ValueError, FileNotFoundError, sqlite3.IntegrityError,
            UnicodeError, OSError) as exc:
        _fail(exc)


@router.get("/{series_id}/evidence-search")
def search_across_books(
    series_id: str,
    query: str = Query(min_length=2, max_length=120),
    min_book: int = Query(default=1, ge=1, le=9999),
    max_book: int = Query(default=9999, ge=1, le=9999),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict:
    """Grounded offline full-series lookup; never infers or approves canon."""
    try:
        return evidence_search.search(series_id, query, min_book=min_book,
                                      max_book=max_book, limit=limit)
    except (ValueError, FileNotFoundError, sqlite3.DatabaseError, OSError) as exc:
        _fail(exc)


@router.get("/{series_id}/characters/{entity_id}/evidence-map")
def character_series_evidence(
    series_id: str, entity_id: str,
    max_book: int = Query(default=9999, ge=1, le=9999),
) -> dict:
    """Read-only character citation-density map across the private series."""
    try:
        return evidence_search.character_evidence_map(
            series_id, entity_id, max_book=max_book)
    except (ValueError, FileNotFoundError, sqlite3.DatabaseError, OSError) as exc:
        _fail(exc)


@router.get("/{series_id}/volumes/{volume_id}/sources")
def list_volume_sources(series_id: str, volume_id: str) -> list[dict]:
    try:
        return vault.volume_sources(series_id, volume_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/extraction-jobs")
def get_extraction_jobs(series_id: str, source_id: str | None = None) -> list[dict]:
    try:
        return extraction_jobs.list_jobs(series_id, source_id=source_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/extraction-jobs", status_code=201)
def start_extraction_job(series_id: str, payload: ExtractionStart) -> dict:
    try:
        return extraction_jobs.create(series_id, payload.source_id, payload.model)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/extraction-jobs/{job_id}")
def get_extraction_job(series_id: str, job_id: str) -> dict:
    try:
        return extraction_jobs.get(series_id, job_id)
    except FileNotFoundError as exc:
        _fail(exc)


@router.post("/{series_id}/extraction-jobs/{job_id}/next")
async def advance_extraction_job(series_id: str, job_id: str) -> dict:
    try:
        return await extraction_jobs.advance(series_id, job_id)
    except TimeoutError as exc:
        raise HTTPException(503, "Local model timed out; the same source window can be retried") from exc
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)
    except (OSError, RuntimeError, httpx.HTTPError) as exc:
        raise HTTPException(503, "Local model unavailable; no source window was advanced") from exc


@router.post("/{series_id}/extraction-jobs/{job_id}/cancel")
def cancel_extraction_job(series_id: str, job_id: str) -> dict:
    try:
        return extraction_jobs.cancel(series_id, job_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/sources/{source_id}/suggest")
async def propose_source_suggestions(series_id: str, source_id: str,
                                      payload: SourceSuggestion) -> dict:
    from .series_suggestions import suggest_facts
    try:
        return await suggest_facts(
            series_id, source_id, payload.start, payload.end, payload.model)
    except TimeoutError as exc:
        raise HTTPException(503, "Local model did not finish. Try a smaller selection.") from exc
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)
    except (ImportError, OSError, RuntimeError) as exc:
        raise HTTPException(503, "Local Ollama is unavailable. Use manual source review.") from exc


@router.get("/{series_id}/sources/{source_id}/excerpt")
def show_source(
    series_id: str, source_id: str, query: str = Query(default="", max_length=400),
    limit: int = Query(default=1200, ge=120, le=5000),
    position: int | None = Query(default=None, ge=0, le=4_000_000),
) -> dict:
    try:
        return vault.list_source_excerpt(series_id, source_id, query, limit,
                                         position=position)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/sources/{source_id}/epub-structure-preview")
async def original_epub_structure_preview(
    series_id: str, source_id: str, file: Annotated[UploadFile, File()],
) -> dict:
    """Preview original EPUB spine against unchanged source; never save or replace canon."""
    try:
        blob = await file.read(vault.MAX_IMPORT_BYTES + 1)
        return series_epub_structure.preview(series_id, source_id, blob)
    except (ValueError, FileNotFoundError, OSError, UnicodeError) as exc:
        _fail(exc)


@router.post("/{series_id}/sources/{source_id}/epub-structure-confirm")
async def confirm_original_epub_structure(
    series_id: str, source_id: str, file: Annotated[UploadFile, File()],
) -> dict:
    """Explicit author acceptance; stores only checked offsets, never EPUB bytes."""
    try:
        blob = await file.read(vault.MAX_IMPORT_BYTES + 1)
        return series_epub_index.save(series_id, source_id, blob)
    except (ValueError, FileNotFoundError, OSError, UnicodeError) as exc:
        _fail(exc)


@router.get("/{series_id}/sources/{source_id}/sections")
def source_section_index(
    series_id: str, source_id: str,
    position: int | None = Query(default=None, ge=0),
) -> dict:
    """Literal chapter-heading coordinates; no invented narrative chronology."""
    from .series_source_sections import sections
    try:
        result = sections(series_id, source_id, position=position)
        saved = series_epub_index.read(series_id, source_id)
        if saved is not None:
            entries = saved["sections"]
            result["sections"] = entries
            result["selected_section"] = next((
                s["index"] for s in entries if position is not None
                and s["start"] <= position < s["end"]
            ), None)
            result["metadata_origin"] = saved["metadata_origin"]
            result["structure_index_saved"] = True
            result["heading_limit_reached"] = len(entries) >= series_epub_structure.MAX_SECTIONS
        return result
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


@router.post("/{series_id}/continuity/check")
def check_scene_continuity(series_id: str, payload: SceneCheck) -> dict:
    from .series_continuity import scan_scene
    try:
        return scan_scene(
            series_id, scene=payload.scene, book=payload.book,
            sequence=payload.sequence,
            assertions=[x.model_dump() for x in payload.assertions],
        )
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/continuity/exceptions")
def get_continuity_exceptions(series_id: str) -> list[dict]:
    from .series_continuity import list_exceptions
    try:
        return list_exceptions(series_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/continuity/exceptions", status_code=201)
def save_continuity_exception(series_id: str, payload: ContinuityException) -> dict:
    from .series_continuity import annotate_exception
    try:
        return annotate_exception(
            series_id, payload.claim_key, payload.reason, payload.note)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.delete("/{series_id}/continuity/exceptions/{claim_key}")
def remove_continuity_exception(series_id: str, claim_key: str) -> dict:
    from .series_continuity import clear_exception
    try:
        return clear_exception(series_id, claim_key)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/consequences/preview")
def preview_series_consequences(series_id: str, payload: ConsequencePreview) -> dict:
    from .series_consequences import preview_change
    try:
        return preview_change(series_id, **payload.model_dump())
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.get("/{series_id}/consequences/reviews")
def series_change_reviews(series_id: str) -> list[dict]:
    from .series_consequences import change_reviews
    try:
        return change_reviews(series_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/consequences/reviews", status_code=201)
def save_series_change_review(series_id: str, payload: ConsequenceSave) -> dict:
    from .series_consequences import save_change_note
    try:
        return save_change_note(series_id, **payload.model_dump())
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/consequences/reviews/{review_id}/dismiss")
def dismiss_series_change_review(series_id: str, review_id: str) -> dict:
    from .series_consequences import dismiss_change
    try:
        return dismiss_change(series_id, review_id)
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)


@router.post("/{series_id}/ember/ask")
async def professional_series_ember(series_id: str, payload: EmberSeriesQuestion) -> dict:
    from .series_ember import ask
    try:
        return await ask(series_id, **payload.model_dump())
    except (ValueError, FileNotFoundError) as exc:
        _fail(exc)
    except TimeoutError as exc:
        raise HTTPException(503, "Local model timed out; try offline series research.") from exc
    except (ImportError, OSError, RuntimeError) as exc:
        raise HTTPException(503, "Local model unavailable; use offline series research.") from exc


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
