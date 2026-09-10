from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from .review_models import (
    ReviewAnnotation,
    ReviewAnnotationCollection,
    ReviewAnnotationCreate,
    ReviewAnnotationUpdate,
)
from .storage import project_root, read_text, utc_now


def _review_path(slug: str) -> Path:
    return project_root(slug) / "review" / "annotations.json"


def _ensure_project(slug: str) -> Path:
    root = project_root(slug)
    if not (root / "project.json").exists():
        raise FileNotFoundError(slug)
    return root


def _digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _load(slug: str) -> ReviewAnnotationCollection:
    _ensure_project(slug)
    path = _review_path(slug)
    if not path.exists():
        return ReviewAnnotationCollection()
    return ReviewAnnotationCollection.model_validate_json(path.read_text(encoding="utf-8"))


def _save(slug: str, collection: ReviewAnnotationCollection) -> None:
    _ensure_project(slug)
    path = _review_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(collection.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _find_anchor(content: str, anchor: str, preferred_start: int | None = None) -> int:
    starts: list[int] = []
    offset = 0
    while True:
        found = content.find(anchor, offset)
        if found < 0:
            break
        starts.append(found)
        offset = found + max(1, len(anchor))
    if not starts:
        return -1
    if preferred_start is None:
        return starts[0]
    return min(starts, key=lambda value: abs(value - preferred_start))


def _with_current_state(slug: str, annotation: ReviewAnnotation) -> ReviewAnnotation:
    try:
        content = read_text(slug, annotation.path)
    except (FileNotFoundError, OSError, UnicodeError, ValueError):
        return annotation.model_copy(
            update={
                "current_start": None,
                "current_end": None,
                "stale": True,
                "reanchored": False,
            }
        )

    digest = _digest(content)
    if digest == annotation.source_hash:
        return annotation.model_copy(
            update={
                "current_start": annotation.source_start,
                "current_end": annotation.source_end,
                "stale": False,
                "reanchored": False,
            }
        )

    start = _find_anchor(content, annotation.anchor_text, annotation.source_start)
    if start < 0:
        return annotation.model_copy(
            update={
                "current_start": None,
                "current_end": None,
                "stale": True,
                "reanchored": False,
            }
        )
    return annotation.model_copy(
        update={
            "current_start": start,
            "current_end": start + len(annotation.anchor_text),
            "stale": False,
            "reanchored": True,
        }
    )


def list_annotations(
    slug: str,
    *,
    path: str | None = None,
    include_resolved: bool = True,
) -> list[ReviewAnnotation]:
    collection = _load(slug)
    result: list[ReviewAnnotation] = []
    for annotation in collection.annotations:
        if path is not None and annotation.path != path:
            continue
        if not include_resolved and annotation.status != "open":
            continue
        result.append(_with_current_state(slug, annotation))
    return sorted(result, key=lambda item: (item.path, item.source_start, item.created_at))


def create_annotation(slug: str, payload: ReviewAnnotationCreate) -> ReviewAnnotation:
    _ensure_project(slug)
    content = read_text(slug, payload.path)
    start = _find_anchor(content, payload.anchor_text, payload.source_start)
    if start < 0:
        raise ValueError(
            "Selected text could not be found in the saved document. Save the document and try again."
        )
    now = utc_now()
    annotation = ReviewAnnotation(
        id=uuid4().hex,
        path=payload.path,
        anchor_text=payload.anchor_text,
        comment=payload.comment.strip(),
        kind=payload.kind,
        status="open",
        author=payload.author.strip(),
        source_hash=_digest(content),
        source_start=start,
        source_end=start + len(payload.anchor_text),
        current_start=start,
        current_end=start + len(payload.anchor_text),
        stale=False,
        reanchored=False,
        created_at=now,
        updated_at=now,
    )
    collection = _load(slug)
    collection.annotations.append(annotation)
    _save(slug, collection)
    return annotation


def update_annotation(
    slug: str,
    annotation_id: str,
    payload: ReviewAnnotationUpdate,
) -> ReviewAnnotation:
    collection = _load(slug)
    for index, annotation in enumerate(collection.annotations):
        if annotation.id != annotation_id:
            continue
        now = utc_now()
        changes: dict = {"updated_at": now}
        if payload.comment is not None:
            changes["comment"] = payload.comment.strip()
        if payload.kind is not None:
            changes["kind"] = payload.kind
        if payload.status is not None:
            changes["status"] = payload.status
            changes["resolved_at"] = now if payload.status == "resolved" else None
        updated = annotation.model_copy(update=changes)
        collection.annotations[index] = updated
        _save(slug, collection)
        return _with_current_state(slug, updated)
    raise FileNotFoundError(annotation_id)


def delete_annotation(slug: str, annotation_id: str) -> None:
    collection = _load(slug)
    remaining = [item for item in collection.annotations if item.id != annotation_id]
    if len(remaining) == len(collection.annotations):
        raise FileNotFoundError(annotation_id)
    collection.annotations = remaining
    _save(slug, collection)
