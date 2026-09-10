from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

EditorialSeverity = Literal["info", "warning", "strong"]
EditorialStatus = Literal["open", "resolved", "ignored"]
EditorialScope = Literal["draft", "document"]


class EditorialReportDefinition(BaseModel):
    id: str
    name: str
    category: str
    description: str
    default_enabled: bool = True


class EditorialProfile(BaseModel):
    enabled_reports: list[str] = Field(default_factory=list)
    long_sentence_words: int = Field(default=35, ge=15, le=100)
    short_sentence_words: int = Field(default=4, ge=1, le=12)
    long_paragraph_words: int = Field(default=180, ge=60, le=600)
    sticky_sentence_percent: float = Field(default=45.0, ge=20.0, le=80.0)
    repeated_phrase_minimum: int = Field(default=3, ge=2, le=12)
    dialogue_low_percent: float = Field(default=5.0, ge=0.0, le=40.0)
    dialogue_high_percent: float = Field(default=65.0, ge=30.0, le=95.0)


class EditorialRunRequest(BaseModel):
    scope: EditorialScope = "draft"
    path: str | None = None
    reports: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def document_requires_path(self) -> EditorialRunRequest:
        if self.scope == "document" and not self.path:
            raise ValueError("Document editorial runs require a path")
        return self


class EditorialFinding(BaseModel):
    id: str
    run_id: str
    report_id: str
    report_name: str
    category: str
    severity: EditorialSeverity
    status: EditorialStatus
    path: str
    binder_node_id: str | None = None
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    line: int = Field(ge=1)
    excerpt: str
    anchor_text: str
    message: str
    suggestion: str
    source_hash: str
    stale: bool = False


class EditorialRunSummary(BaseModel):
    id: str
    created_at: str
    scope: EditorialScope
    path: str | None = None
    reports: list[str]
    project_hash: str
    documents: int = Field(ge=0)
    words: int = Field(ge=0)
    findings: int = Field(ge=0)
    by_report: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    metrics: dict[str, float | int] = Field(default_factory=dict)


class EditorialRunResult(EditorialRunSummary):
    items: list[EditorialFinding] = Field(default_factory=list)


class EditorialFindingStatusUpdate(BaseModel):
    status: EditorialStatus
