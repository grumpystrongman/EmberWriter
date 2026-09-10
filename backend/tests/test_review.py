from __future__ import annotations

import json
from pathlib import Path

from app import review, storage
from app.review_models import ReviewAnnotationCreate, ReviewAnnotationUpdate


def use_temp_data(tmp_path: Path) -> str:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"
    return storage.create_project("Review Test")["slug"]


def test_annotation_persists_and_reanchors_after_source_moves(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    path = "manuscript/chapter-001.md"
    original = "# Chapter 1\n\nThe door opened without a sound. Mara froze.\n"
    storage.save_text(slug, path, original)

    created = review.create_annotation(
        slug,
        ReviewAnnotationCreate(
            path=path,
            anchor_text="The door opened without a sound.",
            comment="Good tension. Consider whether the silence is supernatural.",
            kind="comment",
            author="Editor",
        ),
    )

    assert created.stale is False
    assert created.current_start == created.source_start
    stored = json.loads((storage.project_root(slug) / "review" / "annotations.json").read_text())
    assert stored["annotations"][0]["id"] == created.id

    storage.save_text(slug, path, "# Chapter 1\n\nEarlier that night, rain came hard.\n\n" + original.split("\n\n", 1)[1])
    moved = review.list_annotations(slug, path=path)[0]
    assert moved.stale is False
    assert moved.reanchored is True
    assert moved.current_start is not None
    assert moved.current_start > created.source_start


def test_annotation_becomes_stale_when_anchor_disappears(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    path = "manuscript/chapter-001.md"
    storage.save_text(slug, path, "# Chapter 1\n\nA bell rang twice.\n")
    created = review.create_annotation(
        slug,
        ReviewAnnotationCreate(
            path=path,
            anchor_text="A bell rang twice.",
            comment="Track this setup.",
            kind="todo",
        ),
    )

    storage.save_text(slug, path, "# Chapter 1\n\nThe courtyard was empty.\n")
    current = review.list_annotations(slug, path=path)[0]

    assert current.id == created.id
    assert current.stale is True
    assert current.current_start is None


def test_annotation_status_and_deletion_are_durable(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    path = "manuscript/chapter-001.md"
    storage.save_text(slug, path, "# Chapter 1\n\nMara kept the key.\n")
    created = review.create_annotation(
        slug,
        ReviewAnnotationCreate(
            path=path,
            anchor_text="Mara kept the key.",
            comment="Resolved in chapter four.",
            kind="issue",
        ),
    )

    resolved = review.update_annotation(
        slug,
        created.id,
        ReviewAnnotationUpdate(status="resolved", comment="Payoff verified."),
    )
    assert resolved.status == "resolved"
    assert resolved.resolved_at
    assert review.list_annotations(slug, include_resolved=False) == []

    review.delete_annotation(slug, created.id)
    assert review.list_annotations(slug) == []
