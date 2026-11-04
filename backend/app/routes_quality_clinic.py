"""Local transparent line-aware prose, proofreading and AI-pattern checks."""
from fastapi import APIRouter, HTTPException, Query

from .quality_clinic import check_text
from .storage import get_project, read_text

router = APIRouter(prefix="/api/projects/{slug}/quality-clinic", tags=["Quality Clinic"])


@router.get("/chapters")
def chapters(slug: str) -> list[dict]:
    try:
        project = get_project(slug)
        return [
            {"path": relative}
            for relative in sorted(project["files"])
            if relative.startswith("manuscript/") and relative.lower().endswith((".md", ".txt"))
        ][:250]
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc


@router.get("/inspect")
def inspect(slug: str, path: str = Query(min_length=1, max_length=500)) -> dict:
    try:
        project = get_project(slug)
        if path not in project["files"] or not path.startswith("manuscript/") or not path.endswith((".md", ".txt")):
            raise ValueError("Choose a manuscript document in this project")
        text = read_text(slug, path)
        if len(text.encode("utf-8")) > 1_000_000:
            raise ValueError("Document exceeds the local quality scan limit (1 MB)")
        return {"path": path, **check_text(text)}
    except FileNotFoundError as exc:
        raise HTTPException(404, "Project not found") from exc
    except (OSError, UnicodeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
