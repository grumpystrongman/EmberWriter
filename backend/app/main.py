from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .generation_guard import cancel_generation, guard_generation_request
from .importer import import_project
from .knowledge import ensure_seeded
from .knowledge_scheduler import knowledge_refresh_loop
from .models import (
    FilePayload,
    ProjectCreate,
    ProjectDetail,
    ProjectImport,
    ProjectSummary,
    SearchHit,
    SearchRequest,
)
from .project_recovery import recover_legacy_projects
from .project_restore import restore_uploaded_project
from .revisions import record_revision
from .routes_atlas import router as atlas_router
from .routes_authoring import router as authoring_router
from .routes_binder import router as binder_router
from .routes_board import router as board_router
from .routes_chemistry import router as chemistry_router
from .routes_cover import router as cover_router
from .routes_craft import router as craft_router
from .routes_development import router as development_router
from .routes_distribution import router as distribution_router
from .routes_editorial import router as editorial_router
from .routes_generation import router as generation_router
from .routes_knowledge import router as knowledge_router
from .routes_media import router as media_router
from .routes_memory import router as memory_router
from .routes_models import router as models_router
from .routes_preview import router as preview_router
from .routes_provenance import router as provenance_router
from .routes_reader import router as reader_router
from .routes_review import router as review_router
from .routes_sd import router as sd_router
from .routes_story import router as story_router
from .routes_submissions import router as submissions_router
from .runtime_config import cors_origins
from .storage import (
    PROJECTS_ROOT,
    create_project,
    get_project,
    list_projects,
    list_snapshots,
    read_text,
    restore_snapshot,
    save_text,
    search_story,
)

MAX_PROJECT_RESTORE_FILE_BYTES = 250 * 1024 * 1024
MAX_PROJECT_RESTORE_TOTAL_BYTES = 1024 * 1024 * 1024
_recovery_attempted = False
_last_recovery_report: dict = {
    "attempted": False,
    "found": 0,
    "recovered_count": 0,
    "recovered": [],
    "skipped": [],
    "active_projects_root": str(PROJECTS_ROOT),
    "searched_roots": [],
    "historical_launch_roots": [],
    "drive_wide_scan": False,
}


def _run_project_recovery() -> dict:
    global _last_recovery_report, _recovery_attempted
    _recovery_attempted = True
    try:
        report = recover_legacy_projects()
        report["error"] = None
    except (OSError, UnicodeError, ValueError) as exc:
        report = {
            "attempted": True,
            "found": 0,
            "recovered_count": 0,
            "recovered": [],
            "skipped": [],
            "active_projects_root": str(PROJECTS_ROOT),
            "searched_roots": [],
            "historical_launch_roots": [],
            "drive_wide_scan": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    _last_recovery_report = report
    return report


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_seeded()
    refresh_task = asyncio.create_task(
        knowledge_refresh_loop(), name="ember-knowledge-refresh"
    )
    try:
        yield
    finally:
        refresh_task.cancel()
        with suppress(asyncio.CancelledError):
            await refresh_task


app = FastAPI(title="EmberWriter API", version="0.14.4", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def writer_generation_guard(request: Request, call_next):
    return await guard_generation_request(request, call_next)


app.include_router(generation_router)
app.include_router(models_router)
app.include_router(memory_router)
app.include_router(story_router)
app.include_router(atlas_router)
app.include_router(craft_router)
app.include_router(chemistry_router)
app.include_router(binder_router)
app.include_router(board_router)
app.include_router(authoring_router)
app.include_router(editorial_router)
app.include_router(reader_router)
app.include_router(knowledge_router)
app.include_router(cover_router)
app.include_router(distribution_router)
app.include_router(review_router)
app.include_router(submissions_router)
app.include_router(media_router)
app.include_router(sd_router)
app.include_router(development_router)
app.include_router(preview_router)
app.include_router(provenance_router)


@app.exception_handler(HTTPException)
async def ember_http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if (
        exc.status_code == 502
        and isinstance(detail, str)
        and detail.startswith("Stable Diffusion server error:")
    ):
        detail = (
            "Stable Diffusion could not be reached from EmberWriter. Use the image-server status control to test and auto-detect a local AUTOMATIC1111/Forge API. "
            "If you run AUTOMATIC1111/Forge, start it with the API enabled (normally --api). If EmberWriter runs in Docker/WSL and the image server runs on Windows, expose the WebUI with --listen and use the host address instead of 127.0.0.1."
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail},
        headers=exc.headers,
    )


@app.post("/api/projects/{slug}/generate/cancel")
def cancel_writer_generation(slug: str) -> dict:
    return {"cancelled": cancel_generation(slug)}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "EmberWriter", "version": "0.14.4"}


@app.get("/api/projects", response_model=list[ProjectSummary])
def projects() -> list[dict]:
    # Normal library loading must stay fast and deterministic. The forensic
    # recovery scan walks historical locations and mounted drives; running that
    # automatically here can make a healthy local API look unavailable. Recovery
    # remains available explicitly through POST /api/projects/recover.
    return list_projects()


@app.get("/api/projects/recovery-status")
def project_recovery_status() -> dict:
    return {**_last_recovery_report, "projects_count": len(list_projects())}


@app.post("/api/projects/recover")
def recover_projects() -> dict:
    result = _run_project_recovery()
    result["projects"] = list_projects()
    return result


@app.post("/api/projects", response_model=ProjectDetail)
def new_project(payload: ProjectCreate) -> dict:
    try:
        return create_project(payload.name, payload.description)
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/restore-upload")
async def restore_project_upload(
    files: Annotated[list[UploadFile], File()],
    paths: Annotated[list[str], Form()],
    name: Annotated[str | None, Form()] = None,
) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="Choose an EmberWriter project folder")
    if len(files) != len(paths):
        raise HTTPException(status_code=400, detail="Project folder upload paths are incomplete")

    entries: list[tuple[str, bytes]] = []
    total = 0
    try:
        for upload, relative_path in zip(files, paths, strict=True):
            data = await upload.read(MAX_PROJECT_RESTORE_FILE_BYTES + 1)
            if len(data) > MAX_PROJECT_RESTORE_FILE_BYTES:
                raise ValueError(f"{upload.filename or relative_path} exceeds the 250 MB per-file restore limit")
            total += len(data)
            if total > MAX_PROJECT_RESTORE_TOTAL_BYTES:
                raise ValueError("Project folder exceeds the 1 GB restore limit")
            entries.append((relative_path, data))
        return restore_uploaded_project(entries, name=name)
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/import", response_model=ProjectDetail)
def import_local_project(payload: ProjectImport) -> dict:
    try:
        return import_project(payload.source_path, payload.name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Source path was not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{slug}", response_model=ProjectDetail)
def project(slug: str) -> dict:
    try:
        return get_project(slug)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@app.get("/api/projects/{slug}/file")
def get_file(slug: str, path: str = Query(...)) -> dict:
    try:
        return {"path": path, "content": read_text(slug, path)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/projects/{slug}/file")
def put_file(slug: str, payload: FilePayload, path: str = Query(...)) -> dict:
    try:
        result = save_text(slug, path, payload.content)
        revision = record_revision(slug, path, payload.content, source="save")
        return {**result, "revision": revision}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{slug}/snapshots")
def snapshots(slug: str, path: str | None = None) -> list[dict]:
    return list_snapshots(slug, path)


@app.post("/api/projects/{slug}/snapshots/{snapshot_id}/restore")
def restore(slug: str, snapshot_id: str) -> dict:
    try:
        return restore_snapshot(slug, snapshot_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Snapshot not found") from exc


@app.post("/api/projects/{slug}/search", response_model=list[SearchHit])
def search(slug: str, payload: SearchRequest) -> list[dict]:
    return search_story(slug, payload.query, payload.limit)
