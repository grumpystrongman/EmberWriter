from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .distribution import (
    build_release_package,
    list_release_artifacts,
    load_release_profile,
    save_release_profile,
    validate_release,
)
from .release_models import (
    ReleaseArtifact,
    ReleaseBuildResponse,
    ReleaseProfile,
    ReleaseValidationResponse,
)

router = APIRouter(prefix="/api/projects/{slug}/distribution")


@router.get("/profile", response_model=ReleaseProfile)
def get_profile(slug: str) -> ReleaseProfile:
    try:
        return load_release_profile(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/profile", response_model=ReleaseProfile)
def put_profile(slug: str, payload: ReleaseProfile) -> ReleaseProfile:
    try:
        return save_release_profile(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/artifacts", response_model=list[ReleaseArtifact])
def artifacts(slug: str) -> list[ReleaseArtifact]:
    try:
        return list_release_artifacts(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/validate", response_model=ReleaseValidationResponse)
def validate(slug: str, payload: ReleaseProfile) -> ReleaseValidationResponse:
    try:
        return validate_release(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project or release artifact not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/build", response_model=ReleaseBuildResponse)
def build(slug: str, payload: ReleaseProfile) -> ReleaseBuildResponse:
    try:
        return build_release_package(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project or release artifact not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
