from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .models import ProviderConfig

SubmissionMethod = Literal["email", "query_manager", "web_form", "postal", "other"]
SubmissionTargetKind = Literal["agent", "publisher", "editor", "contest", "other"]
SampleKind = Literal["none", "pages", "chapters", "words", "full"]
AttachmentMode = Literal["body", "attachments", "mixed"]
SubmissionStatus = Literal[
    "draft",
    "ready",
    "sent",
    "partial_requested",
    "full_requested",
    "revision_requested",
    "offer",
    "pass",
    "withdrawn",
]
ManuscriptPreset = Literal["standard_novel", "shunn_classic"]
SubmissionMaterialKind = Literal["query", "synopsis", "pitch", "bio"]


class SubmissionDestination(BaseModel):
    id: str
    name: str = Field(min_length=1, max_length=240)
    kind: SubmissionTargetKind = "agent"
    contact_name: str = Field(default="", max_length=240)
    email: str = Field(default="", max_length=320)
    submission_url: str = Field(default="", max_length=2000)
    guidelines_url: str = Field(default="", max_length=2000)
    method: SubmissionMethod = "email"
    query_required: bool = True
    synopsis_required: bool = False
    bio_required: bool = False
    sample_kind: SampleKind = "pages"
    sample_count: int = Field(default=10, ge=0, le=100000)
    attachment_mode: AttachmentMode = "body"
    accepted_formats: list[str] = Field(default_factory=lambda: ["docx"])
    simultaneous_submissions_allowed: bool | None = None
    expected_response_days: int | None = Field(default=None, ge=1, le=730)
    notes: str = Field(default="", max_length=12000)


class SubmissionRecord(BaseModel):
    id: str
    destination_id: str
    status: SubmissionStatus = "draft"
    package_id: str = ""
    submitted_at: str = ""
    follow_up_on: str = ""
    response_at: str = ""
    notes: str = Field(default="", max_length=12000)
    created_at: str
    updated_at: str


class SubmissionRecordUpdate(BaseModel):
    status: SubmissionStatus | None = None
    submitted_at: str | None = None
    follow_up_on: str | None = None
    response_at: str | None = None
    notes: str | None = Field(default=None, max_length=12000)


class SubmissionProfile(BaseModel):
    schema_version: int = 1
    author_name: str = Field(default="", max_length=240)
    email: str = Field(default="", max_length=320)
    phone: str = Field(default="", max_length=80)
    address: str = Field(default="", max_length=1000)
    website: str = Field(default="", max_length=1000)
    title: str = Field(default="", max_length=400)
    genre: str = Field(default="", max_length=240)
    word_count: int = Field(default=0, ge=0)
    logline: str = Field(default="", max_length=3000)
    pitch: str = Field(default="", max_length=12000)
    query_letter: str = Field(default="", max_length=30000)
    synopsis: str = Field(default="", max_length=100000)
    bio: str = Field(default="", max_length=12000)
    comp_titles: list[str] = Field(default_factory=list, max_length=20)
    manuscript_preset: ManuscriptPreset = "standard_novel"
    destinations: list[SubmissionDestination] = Field(default_factory=list)
    records: list[SubmissionRecord] = Field(default_factory=list)


class SubmissionValidationIssue(BaseModel):
    level: Literal["error", "warning", "info"]
    code: str
    message: str
    destination_id: str | None = None


class SubmissionValidationResponse(BaseModel):
    valid: bool
    issues: list[SubmissionValidationIssue] = Field(default_factory=list)
    destination_id: str
    sample_description: str = ""


class SubmissionBuildRequest(BaseModel):
    destination_id: str = Field(min_length=1)
    profile: SubmissionProfile


class SubmissionPackageArtifact(BaseModel):
    format: Literal["zip", "json", "docx", "pdf", "txt"]
    filename: str
    relative_path: str
    bytes: int


class SubmissionBuildResponse(BaseModel):
    package_id: str
    validation: SubmissionValidationResponse
    artifacts: list[SubmissionPackageArtifact] = Field(default_factory=list)
    included_files: list[str] = Field(default_factory=list)
    profile: SubmissionProfile | None = None


class SubmissionMaterialDraftRequest(BaseModel):
    kind: SubmissionMaterialKind
    provider: ProviderConfig
    destination_id: str | None = None
    profile: SubmissionProfile


class SubmissionMaterialDraftResponse(BaseModel):
    kind: SubmissionMaterialKind
    text: str
    context_documents: int
    used_story_summaries: bool
