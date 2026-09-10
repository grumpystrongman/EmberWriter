from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReviewKind = Literal["comment", "question", "issue", "todo", "praise"]
ReviewStatus = Literal["open", "resolved", "dismissed"]


class ReviewAnnotationCreate(BaseModel):
    path: str = Field(min_length=1)
    anchor_text: str = Field(min_length=1, max_length=12000)
    comment: str = Field(min_length=1, max_length=12000)
    kind: ReviewKind = "comment"
    author: str = Field(default="", max_length=160)
    source_start: int | None = Field(default=None, ge=0)


class ReviewAnnotationUpdate(BaseModel):
    comment: str | None = Field(default=None, min_length=1, max_length=12000)
    kind: ReviewKind | None = None
    status: ReviewStatus | None = None


class ReviewAnnotation(BaseModel):
    id: str
    path: str
    anchor_text: str
    comment: str
    kind: ReviewKind
    status: ReviewStatus
    author: str = ""
    source_hash: str
    source_start: int
    source_end: int
    current_start: int | None = None
    current_end: int | None = None
    stale: bool = False
    reanchored: bool = False
    created_at: str
    updated_at: str
    resolved_at: str | None = None


class ReviewAnnotationCollection(BaseModel):
    schema_version: int = 1
    annotations: list[ReviewAnnotation] = Field(default_factory=list)
