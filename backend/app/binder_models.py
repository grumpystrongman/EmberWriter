from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

BinderNodeKind = Literal[
    "folder",
    "document",
    "research",
    "character",
    "location",
    "note",
    "trash",
]


class BinderNode(BaseModel):
    id: str
    title: str = Field(min_length=1, max_length=240)
    kind: BinderNodeKind
    parent_id: str | None = None
    position: int = Field(default=0, ge=0)
    path: str | None = None
    synopsis: str = Field(default="", max_length=8000)
    label: str = Field(default="")
    status: str = Field(default="")
    keywords: list[str] = Field(default_factory=list)
    include_in_compile: bool = True
    target_words: int | None = Field(default=None, ge=0)
    custom_metadata: dict[str, Any] = Field(default_factory=dict)
    previous_parent_id: str | None = None
    created_at: str
    updated_at: str
    word_count: int = Field(default=0, ge=0)


class BinderCollection(BaseModel):
    id: str
    name: str = Field(min_length=1, max_length=160)
    node_ids: list[str] = Field(default_factory=list)
    query: str = Field(default="", max_length=1000)
    created_at: str
    updated_at: str


class BinderState(BaseModel):
    schema_version: int = 1
    project_slug: str = ""
    roots: list[str] = Field(default_factory=list)
    nodes: list[BinderNode] = Field(default_factory=list)
    collections: list[BinderCollection] = Field(default_factory=list)


class BinderNodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    kind: BinderNodeKind = "document"
    parent_id: str | None = None
    path: str | None = None
    synopsis: str = Field(default="", max_length=8000)
    label: str = ""
    status: str = ""
    keywords: list[str] = Field(default_factory=list)
    include_in_compile: bool = True
    target_words: int | None = Field(default=None, ge=0)
    custom_metadata: dict[str, Any] = Field(default_factory=dict)


class BinderNodeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    parent_id: str | None = None
    synopsis: str | None = Field(default=None, max_length=8000)
    label: str | None = None
    status: str | None = None
    keywords: list[str] | None = None
    include_in_compile: bool | None = None
    target_words: int | None = Field(default=None, ge=0)
    custom_metadata: dict[str, Any] | None = None


class BinderReorderRequest(BaseModel):
    parent_id: str | None = None
    node_ids: list[str] = Field(min_length=1)


class BinderCollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    node_ids: list[str] = Field(default_factory=list)
    query: str = Field(default="", max_length=1000)


class BinderCollectionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    node_ids: list[str] | None = None
    query: str | None = Field(default=None, max_length=1000)
