from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RetailerTarget = Literal["kdp", "ingramspark", "apple_books", "kobo", "direct"]
EditionFormat = Literal["ebook", "paperback", "hardcover"]
IdentifierMode = Literal["own", "retailer_assigned", "none"]
RightsScope = Literal["worldwide", "territories"]
ContributorRole = Literal["author", "editor", "illustrator", "translator", "other"]


class Contributor(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    role: ContributorRole = "other"


class ReleaseEdition(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    format: EditionFormat
    enabled: bool = True
    retailers: list[RetailerTarget] = Field(default_factory=list, max_length=5)
    identifier_mode: IdentifierMode = "none"
    isbn: str = Field(default="", max_length=32)
    price: float = Field(default=0.0, ge=0.0, le=10000.0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    interior_path: str = Field(default="", max_length=800)
    cover_path: str = Field(default="", max_length=800)
    trim_width: float = Field(default=6.0, ge=4.0, le=8.5)
    trim_height: float = Field(default=9.0, ge=6.0, le=11.7)
    page_count: int = Field(default=300, ge=1, le=5000)
    drm: bool = False
    expanded_distribution: bool = False


class ReleaseProfile(BaseModel):
    schema_version: int = 1
    title: str = Field(default="Untitled", max_length=240)
    subtitle: str = Field(default="", max_length=400)
    series_name: str = Field(default="", max_length=240)
    series_number: str = Field(default="", max_length=40)
    author: str = Field(default="", max_length=240)
    contributors: list[Contributor] = Field(default_factory=list, max_length=32)
    publisher: str = Field(default="", max_length=240)
    imprint: str = Field(default="", max_length=240)
    description: str = Field(default="", max_length=12000)
    short_description: str = Field(default="", max_length=2000)
    author_bio: str = Field(default="", max_length=6000)
    language: str = Field(default="en", min_length=2, max_length=35)
    publication_date: str = Field(default="", max_length=20)
    release_date: str = Field(default="", max_length=20)
    original_publication_date: str = Field(default="", max_length=20)
    explicit_content: bool = False
    public_domain: bool = False
    reading_age_min: int | None = Field(default=None, ge=0, le=120)
    reading_age_max: int | None = Field(default=None, ge=0, le=120)
    rights_scope: RightsScope = "worldwide"
    territories: list[str] = Field(default_factory=list, max_length=256)
    keywords: list[str] = Field(default_factory=list, max_length=32)
    kdp_categories: list[str] = Field(default_factory=list, max_length=12)
    bisac_codes: list[str] = Field(default_factory=list, max_length=12)
    thema_codes: list[str] = Field(default_factory=list, max_length=12)
    apple_categories: list[str] = Field(default_factory=list, max_length=12)
    kobo_categories: list[str] = Field(default_factory=list, max_length=12)
    editions: list[ReleaseEdition] = Field(default_factory=list, max_length=12)


class ReleaseArtifact(BaseModel):
    relative_path: str
    filename: str
    suffix: str
    bytes: int
    sha256: str
    role: Literal["ebook_interior", "print_interior", "cover", "editorial", "unknown"]
    modified_at: str


class ReleaseValidationIssue(BaseModel):
    level: Literal["error", "warning", "info"]
    code: str
    message: str
    retailer: RetailerTarget | None = None
    edition_id: str | None = None
    authority: str = ""
    authority_url: str = ""


class ReleaseValidationResponse(BaseModel):
    valid: bool
    issues: list[ReleaseValidationIssue] = Field(default_factory=list)
    enabled_editions: int
    selected_retailers: list[RetailerTarget] = Field(default_factory=list)


class ReleaseManifestFile(BaseModel):
    edition_id: str
    role: Literal["interior", "cover"]
    source_path: str
    package_path: str
    bytes: int
    sha256: str


class ReleasePackageArtifact(BaseModel):
    format: Literal["zip", "json", "csv"]
    filename: str
    relative_path: str
    bytes: int


class ReleaseBuildResponse(BaseModel):
    release_id: str
    validation: ReleaseValidationResponse
    manifest_files: list[ReleaseManifestFile] = Field(default_factory=list)
    artifacts: list[ReleasePackageArtifact] = Field(default_factory=list)
