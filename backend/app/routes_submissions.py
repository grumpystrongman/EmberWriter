from __future__ import annotations

from http.client import HTTPException as HTTPClientError

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .submission_guidelines import extract_guidelines, fetch_html
from .submission_market import book_publisher_catalog, market_listings, watch_publisher
from .submission_models import (
    SubmissionBuildRequest,
    SubmissionBuildResponse,
    SubmissionMaterialDraftRequest,
    SubmissionMaterialDraftResponse,
    SubmissionProfile,
    SubmissionRecordUpdate,
    SubmissionValidationResponse,
)
from .submissions import (
    build_submission_package,
    draft_submission_material,
    load_submission_profile,
    save_submission_profile,
    update_submission_record,
    validate_submission,
)

router = APIRouter(prefix="/api")


@router.get("/submissions/market")
def get_market() -> list[dict]:
    return market_listings()


@router.get("/submissions/publisher-catalog")
def publisher_catalog() -> list[dict]:
    return book_publisher_catalog()


class GuidelinesImport(BaseModel):
    publisher_name: str = Field(default="", max_length=200)
    url: str = Field(min_length=1, max_length=2000)


@router.post("/submissions/import-guidelines")
def import_guidelines(payload: GuidelinesImport) -> dict:
    try:
        guidelines = extract_guidelines(fetch_html(payload.url))
        if payload.publisher_name.strip():
            watch_publisher(payload.publisher_name.strip(), payload.url, guidelines)
        return guidelines
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (OSError, HTTPClientError) as exc:
        raise HTTPException(
            status_code=400, detail="The guidelines page could not be reached. Paste its requirements manually.",
        ) from exc


@router.get("/projects/{slug}/submissions/profile", response_model=SubmissionProfile)
def get_profile(slug: str) -> SubmissionProfile:
    try:
        return load_submission_profile(slug)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/projects/{slug}/submissions/profile", response_model=SubmissionProfile)
def put_profile(slug: str, payload: SubmissionProfile) -> SubmissionProfile:
    try:
        return save_submission_profile(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/projects/{slug}/submissions/validate",
    response_model=SubmissionValidationResponse,
)
def validate(slug: str, payload: SubmissionBuildRequest) -> SubmissionValidationResponse:
    try:
        return validate_submission(slug, payload.profile, payload.destination_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project or submission destination not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{slug}/submissions/build", response_model=SubmissionBuildResponse)
def build(slug: str, payload: SubmissionBuildRequest) -> SubmissionBuildResponse:
    try:
        response, profile = build_submission_package(
            slug,
            profile=payload.profile,
            destination_id=payload.destination_id,
        )
        return response.model_copy(update={"profile": profile})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project or submission destination not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/projects/{slug}/submissions/draft",
    response_model=SubmissionMaterialDraftResponse,
)
async def draft(slug: str, payload: SubmissionMaterialDraftRequest) -> SubmissionMaterialDraftResponse:
    try:
        text, documents, used_summaries = await draft_submission_material(
            slug,
            kind=payload.kind,
            provider=payload.provider,
            profile=payload.profile,
            destination_id=payload.destination_id,
        )
        return SubmissionMaterialDraftResponse(
            kind=payload.kind,
            text=text,
            context_documents=documents,
            used_story_summaries=used_summaries,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project or submission destination not found") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Model server error: {exc}") from exc
    except (OSError, TypeError, UnicodeError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/projects/{slug}/submissions/records/{record_id}", response_model=SubmissionProfile)
def patch_record(
    slug: str,
    record_id: str,
    payload: SubmissionRecordUpdate,
) -> SubmissionProfile:
    try:
        profile = load_submission_profile(slug)
        return update_submission_record(
            slug,
            profile,
            record_id,
            status=payload.status,
            submitted_at=payload.submitted_at,
            follow_up_on=payload.follow_up_on,
            response_at=payload.response_at,
            notes=payload.notes,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Submission record not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
