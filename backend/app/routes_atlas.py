from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Query

from .atlas import (
    advise_atlas,
    atlas_state,
    bootstrap_atlas,
    calculate_route,
    compare_routes,
    load_atlas,
    save_atlas,
)
from .atlas_models import (
    AtlasAdviceRequest,
    AtlasAdviceResponse,
    AtlasBootstrapRequest,
    AtlasBootstrapResponse,
    AtlasRouteCompareRequest,
    AtlasRouteCompareResponse,
    AtlasRouteRequest,
    AtlasRouteResult,
    StoryAtlas,
)

router = APIRouter(prefix="/api")


@router.get("/projects/{slug}/atlas", response_model=StoryAtlas)
def get_atlas(slug: str) -> StoryAtlas:
    try:
        return load_atlas(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/projects/{slug}/atlas", response_model=StoryAtlas)
def put_atlas(slug: str, payload: StoryAtlas) -> StoryAtlas:
    try:
        return save_atlas(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/projects/{slug}/atlas/state")
def get_atlas_state(
    slug: str,
    chapter: int = Query(default=0, ge=0, le=1_000_000),
    character: str = Query(default="", max_length=200),
) -> dict:
    try:
        return atlas_state(load_atlas(slug), chapter=chapter, character=character)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/atlas/route", response_model=AtlasRouteResult)
def route(slug: str, payload: AtlasRouteRequest) -> AtlasRouteResult:
    try:
        return calculate_route(load_atlas(slug), payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/projects/{slug}/atlas/routes/compare",
    response_model=AtlasRouteCompareResponse,
)
def routes_compare(slug: str, payload: AtlasRouteCompareRequest) -> AtlasRouteCompareResponse:
    try:
        return compare_routes(load_atlas(slug), payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/atlas/advise", response_model=AtlasAdviceResponse)
async def atlas_advice(slug: str, payload: AtlasAdviceRequest) -> AtlasAdviceResponse:
    try:
        return await advise_atlas(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/projects/{slug}/atlas/bootstrap", response_model=AtlasBootstrapResponse)
async def atlas_bootstrap(slug: str, payload: AtlasBootstrapRequest) -> AtlasBootstrapResponse:
    try:
        return await bootstrap_atlas(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
