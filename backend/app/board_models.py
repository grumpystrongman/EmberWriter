from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

BoardItemKind = Literal["sticky", "image", "attachment", "link", "binder"]


class BoardItem(BaseModel):
    id: str
    kind: BoardItemKind
    title: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=50000)
    x: float = 80
    y: float = 80
    width: float = Field(default=260, ge=120, le=1200)
    height: float = Field(default=180, ge=80, le=1000)
    z: int = Field(default=1, ge=0, le=1000000)
    color: str = Field(default="amber", max_length=40)
    asset_path: str = Field(default="", max_length=2000)
    original_filename: str = Field(default="", max_length=1000)
    url: str = Field(default="", max_length=4000)
    binder_node_id: str = Field(default="", max_length=200)
    created_at: str
    updated_at: str


class BoardState(BaseModel):
    schema_version: int = 1
    items: list[BoardItem] = Field(default_factory=list)


class BoardItemCreate(BaseModel):
    kind: BoardItemKind
    title: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=50000)
    x: float = 80
    y: float = 80
    width: float = Field(default=260, ge=120, le=1200)
    height: float = Field(default=180, ge=80, le=1000)
    color: str = Field(default="amber", max_length=40)
    url: str = Field(default="", max_length=4000)
    binder_node_id: str = Field(default="", max_length=200)


class BoardItemUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=50000)
    x: float | None = None
    y: float | None = None
    width: float | None = Field(default=None, ge=120, le=1200)
    height: float | None = Field(default=None, ge=80, le=1000)
    z: int | None = Field(default=None, ge=0, le=1000000)
    color: str | None = Field(default=None, max_length=40)
    url: str | None = Field(default=None, max_length=4000)
    binder_node_id: str | None = Field(default=None, max_length=200)
