from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .importer import import_project
from .models import FilePayload, ProjectCreate, ProjectDetail, ProjectImport, ProjectSummary, SearchHit, SearchRequest
from .routes_generation import router as generation_router
from .storage import (
    create_project,
    get_project,
    list_projects,
    list_snapshots,
    read_text,
    restore_snapshot,
    save_text,
    search_story,
)

app = FastAPI(title="EmberWriter API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(generation_router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "EmberWriter", "version": "0.1.0"}


@app.get("/api/projects", response_model=list[ProjectSummary])
def projects() -> list[dict]:
    return list_projects()


@app.post("/api/projects", response_model=ProjectDetail)
def new_project(payload: ProjectCreate) -> dict:
    try:
        return create_project(payload.name, payload.description)
    except (OSError, ValueError) as exc:
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
        return save_text(slug, path, payload.content)
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
