from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from .cover_models import (
    CoverAsset,
    CoverExportResponse,
    CoverGeometry,
    CoverProfile,
    CoverValidationResponse,
)
from .covers import (
    cover_geometry,
    export_cover,
    load_cover_profile,
    save_cover_asset,
    save_cover_profile,
    validate_cover,
)

router = APIRouter(prefix="/api/projects/{slug}/cover")
MAX_COVER_ASSET_BYTES = 100 * 1024 * 1024


@router.get("/profile", response_model=CoverProfile)
def get_profile(slug: str) -> CoverProfile:
    try:
        return load_cover_profile(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/profile", response_model=CoverProfile)
def put_profile(slug: str, payload: CoverProfile) -> CoverProfile:
    try:
        return save_cover_profile(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/geometry", response_model=CoverGeometry)
def geometry(slug: str, payload: CoverProfile) -> CoverGeometry:
    try:
        load_cover_profile(slug)
        return cover_geometry(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/validate", response_model=CoverValidationResponse)
def validate(slug: str, payload: CoverProfile) -> CoverValidationResponse:
    try:
        return validate_cover(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project or cover asset not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/assets", response_model=CoverAsset)
async def upload_asset(
    slug: str,
    file: Annotated[UploadFile, File()],
) -> CoverAsset:
    try:
        data = await file.read(MAX_COVER_ASSET_BYTES + 1)
        if len(data) > MAX_COVER_ASSET_BYTES:
            raise ValueError("Cover artwork exceeds the 100 MB upload limit")
        return save_cover_asset(slug, file.filename or "cover.png", data)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/export", response_model=CoverExportResponse)
def build_cover(slug: str, payload: CoverProfile) -> CoverExportResponse:
    try:
        return export_cover(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project or cover asset not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
