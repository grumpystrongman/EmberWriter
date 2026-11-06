"""Discover and instantiate author-selected writing format templates."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .writing_templates import assignment, catalog, create, preview

router = APIRouter(prefix="/api")


class TemplatePreview(BaseModel):
    template_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=160)


@router.get("/writing-templates")
def list_templates() -> list[dict]:
    return catalog()


@router.post("/writing-templates/preview")
def preview_template(payload: TemplatePreview) -> dict:
    try:
        return preview(payload.template_id, payload.title)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/projects/{slug}/writing-templates/assignment")
def writing_assignment(slug: str, path: str = Query(min_length=1, max_length=500)) -> dict:
    try:
        return assignment(slug, path)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/projects/{slug}/writing-templates", status_code=201)
def apply_template(slug: str, payload: TemplatePreview) -> dict:
    try:
        return create(slug, payload.template_id, payload.title)
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
