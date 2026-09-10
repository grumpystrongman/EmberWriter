from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from .chemistry import (
    analyze_aftermath,
    apply_aftermath,
    infer_chemistry,
    list_chemistry_profiles,
    save_chemistry_profile,
)
from .models import (
    AftermathAnalyzeRequest,
    AftermathApplyResponse,
    AftermathProposal,
    ChemistryInferRequest,
    ChemistryInferResponse,
    RelationshipChemistryProfile,
)

router = APIRouter(prefix="/api")


@router.get(
    "/projects/{slug}/chemistry",
    response_model=list[RelationshipChemistryProfile],
)
def chemistry_profiles(slug: str) -> list[RelationshipChemistryProfile]:
    try:
        return list_chemistry_profiles(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.put(
    "/projects/{slug}/chemistry",
    response_model=RelationshipChemistryProfile,
)
def update_chemistry(
    slug: str,
    payload: RelationshipChemistryProfile,
) -> RelationshipChemistryProfile:
    try:
        profile, _ = save_chemistry_profile(slug, payload)
        return profile
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/projects/{slug}/chemistry/infer",
    response_model=ChemistryInferResponse,
)
async def infer_relationship_chemistry(
    slug: str,
    payload: ChemistryInferRequest,
) -> dict:
    try:
        return await infer_chemistry(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/projects/{slug}/aftermath/analyze",
    response_model=AftermathProposal,
)
async def analyze_scene_aftermath(
    slug: str,
    payload: AftermathAnalyzeRequest,
) -> AftermathProposal:
    try:
        return await analyze_aftermath(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/projects/{slug}/aftermath/apply",
    response_model=AftermathApplyResponse,
)
def apply_scene_aftermath(
    slug: str,
    payload: AftermathProposal,
) -> AftermathApplyResponse:
    try:
        profiles, paths = apply_aftermath(slug, payload)
        return AftermathApplyResponse(profiles=profiles, saved_paths=paths)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
