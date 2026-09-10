from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CoverPlatform = Literal["kdp_paperback", "ingramspark", "custom_print", "kdp_ebook"]
PaperType = Literal["white_bw", "cream_bw", "premium_color", "standard_color"]
ArtworkMode = Literal["front", "full_wrap"]
BarcodeMode = Literal["platform", "custom", "none"]
TextAlign = Literal["left", "center", "right"]


class CoverProfile(BaseModel):
    schema_version: int = 1
    platform: CoverPlatform = "kdp_paperback"
    title: str = Field(default="Untitled", max_length=240)
    subtitle: str = Field(default="", max_length=400)
    author: str = Field(default="", max_length=240)
    back_blurb: str = Field(default="", max_length=12000)
    imprint: str = Field(default="", max_length=240)
    isbn: str = Field(default="", max_length=40)

    trim_width: float = Field(default=6.0, ge=4.0, le=8.5)
    trim_height: float = Field(default=9.0, ge=6.0, le=11.7)
    page_count: int = Field(default=300, ge=1, le=2000)
    paper_type: PaperType = "white_bw"
    manual_spine_width: float = Field(default=0.0, ge=0.0, le=5.0)
    bleed: float = Field(default=0.125, ge=0.0, le=0.5)
    safe_inset: float = Field(default=0.125, ge=0.0, le=1.0)
    spine_safe_inset: float = Field(default=0.0625, ge=0.0, le=0.5)

    ebook_width_px: int = Field(default=1600, ge=625, le=10000)
    ebook_height_px: int = Field(default=2560, ge=1000, le=10000)

    background_color: str = "#15100d"
    front_overlay_color: str = "#1c1410"
    back_overlay_color: str = "#18110e"
    spine_color: str = "#25170f"
    title_color: str = "#f3e7da"
    subtitle_color: str = "#d7b99f"
    author_color: str = "#f0d5bf"
    body_color: str = "#eadfd6"

    title_font: Literal["Helvetica", "Times", "Courier"] = "Times"
    body_font: Literal["Helvetica", "Times", "Courier"] = "Times"
    title_size: float = Field(default=34.0, ge=7.0, le=120.0)
    subtitle_size: float = Field(default=16.0, ge=7.0, le=72.0)
    author_size: float = Field(default=16.0, ge=7.0, le=72.0)
    body_size: float = Field(default=10.5, ge=7.0, le=30.0)
    spine_size: float = Field(default=10.0, ge=7.0, le=30.0)
    title_align: TextAlign = "center"
    blurb_align: TextAlign = "left"

    artwork_path: str = Field(default="", max_length=500)
    artwork_mode: ArtworkMode = "front"
    artwork_opacity: float = Field(default=1.0, ge=0.0, le=1.0)

    spine_text: str = Field(default="", max_length=500)
    barcode_mode: BarcodeMode = "platform"
    barcode_path: str = Field(default="", max_length=500)
    barcode_width: float = Field(default=2.0, ge=0.75, le=3.0)
    barcode_height: float = Field(default=1.2, ge=0.5, le=2.0)
    barcode_margin: float = Field(default=0.25, ge=0.05, le=1.0)


class CoverGeometry(BaseModel):
    platform: CoverPlatform
    trim_width: float
    trim_height: float
    page_count: int
    bleed: float
    spine_width: float
    cover_width: float
    cover_height: float
    back_x: float
    spine_x: float
    front_x: float
    safe_inset: float
    spine_safe_inset: float
    spine_text_allowed: bool
    exact_platform_formula: bool
    authority: str
    authority_url: str
    notes: list[str] = Field(default_factory=list)


class CoverValidationIssue(BaseModel):
    level: Literal["error", "warning", "info"]
    code: str
    message: str


class CoverValidationResponse(BaseModel):
    valid: bool
    geometry: CoverGeometry
    issues: list[CoverValidationIssue] = Field(default_factory=list)


class CoverAsset(BaseModel):
    relative_path: str
    filename: str
    width_px: int
    height_px: int
    format: str
    bytes: int


class CoverArtifact(BaseModel):
    format: Literal["pdf", "jpg", "png"]
    filename: str
    relative_path: str
    bytes: int
    width: float | int
    height: float | int
    units: Literal["in", "px"]


class CoverExportResponse(BaseModel):
    export_id: str
    platform: CoverPlatform
    geometry: CoverGeometry
    validation: CoverValidationResponse
    artifacts: list[CoverArtifact] = Field(default_factory=list)
