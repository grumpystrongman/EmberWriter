from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from .review import create_annotation, delete_annotation, list_annotations, update_annotation
from .review_models import ReviewAnnotation, ReviewAnnotationCreate, ReviewAnnotationUpdate

router = APIRouter(prefix="/api")


@router.get("/projects/{slug}/review/annotations", response_model=list[ReviewAnnotation])
def annotations(
    slug: str,
    path: Annotated[str | None, Query()] = None,
    include_resolved: Annotated[bool, Query()] = True,
) -> list[ReviewAnnotation]:
    try:
        return list_annotations(slug, path=path, include_resolved=include_resolved)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.post("/projects/{slug}/review/annotations", response_model=ReviewAnnotation)
def add_annotation(slug: str, payload: ReviewAnnotationCreate) -> ReviewAnnotation:
    try:
        return create_annotation(slug, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project or document not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/projects/{slug}/review/annotations/{annotation_id}", response_model=ReviewAnnotation)
def edit_annotation(
    slug: str,
    annotation_id: str,
    payload: ReviewAnnotationUpdate,
) -> ReviewAnnotation:
    try:
        return update_annotation(slug, annotation_id, payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Annotation not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/projects/{slug}/review/annotations/{annotation_id}", status_code=204)
def remove_annotation(slug: str, annotation_id: str) -> Response:
    try:
        delete_annotation(slug, annotation_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Annotation not found") from exc
    return Response(status_code=204)
