from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image
from pypdf import PdfReader

from app import covers, routes_cover, storage
from app.cover_models import CoverProfile


def use_temp_data(tmp_path: Path) -> str:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"
    return storage.create_project("Cover Test")["slug"]


def png_bytes(size: tuple[int, int], color: str) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_kdp_paperback_geometry_matches_current_formula(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    profile = CoverProfile(
        title="A Book",
        platform="kdp_paperback",
        trim_width=6,
        trim_height=9,
        page_count=300,
        paper_type="white_bw",
    )

    geometry = covers.cover_geometry(profile)

    assert slug
    assert geometry.spine_width == pytest.approx(0.6756)
    assert geometry.cover_width == pytest.approx(12.9256)
    assert geometry.cover_height == pytest.approx(9.25)
    assert geometry.back_x == pytest.approx(0.125)
    assert geometry.front_x == pytest.approx(6.8006)
    assert geometry.bleed == pytest.approx(0.125)
    assert geometry.spine_safe_inset >= 0.0625
    assert geometry.spine_text_allowed is True
    assert geometry.exact_platform_formula is True
    assert geometry.authority_url.startswith("https://kdp.amazon.com/")


def test_kdp_spine_text_is_blocked_below_80_pages(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    profile = CoverProfile(
        title="Short Book",
        platform="kdp_paperback",
        trim_width=6,
        trim_height=9,
        page_count=79,
        paper_type="cream_bw",
        spine_text="Short Book · A. Writer",
    )

    validation = covers.validate_cover(slug, profile)

    assert validation.valid is False
    assert validation.geometry.spine_width == pytest.approx(0.1975)
    assert any(issue.code == "spine-text-page-count" for issue in validation.issues)
    with pytest.raises(ValueError, match="spine text"):
        covers.export_cover(slug, profile)


def test_cover_profile_persists_as_portable_json(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    profile = CoverProfile(
        title="Persistent Cover",
        subtitle="A subtitle",
        author="A. Writer",
        back_blurb="A dangerous bargain changes everything.",
        platform="custom_print",
        manual_spine_width=0.72,
        trim_width=5.5,
        trim_height=8.5,
    )

    covers.save_cover_profile(slug, profile)
    loaded = covers.load_cover_profile(slug)
    path = storage.project_root(slug) / "publishing" / "cover-profile.json"

    assert path.is_file()
    assert loaded == profile
    assert "Persistent Cover" in path.read_text(encoding="utf-8")


def test_ingram_mode_requires_template_spine_and_uses_its_own_spine_text_threshold(
    tmp_path: Path,
) -> None:
    slug = use_temp_data(tmp_path)
    missing = CoverProfile(title="Template Book", platform="ingramspark", manual_spine_width=0)
    complete = missing.model_copy(update={"manual_spine_width": 0.63})
    too_short = complete.model_copy(update={"page_count": 47, "spine_text": "Template Book"})
    eligible = complete.model_copy(update={"page_count": 60, "spine_text": "Template Book"})

    invalid = covers.validate_cover(slug, missing)
    short_validation = covers.validate_cover(slug, too_short)
    valid = covers.validate_cover(slug, eligible)

    assert invalid.valid is False
    assert any(issue.code == "ingram-template-spine" for issue in invalid.issues)
    assert short_validation.valid is False
    assert any(issue.code == "ingram-spine-text" for issue in short_validation.issues)
    assert valid.valid is True
    assert valid.geometry.spine_width == pytest.approx(0.63)
    assert valid.geometry.spine_text_allowed is True
    assert valid.geometry.exact_platform_formula is False
    assert "CoverTemplateGenerator" in valid.geometry.authority_url


def test_cover_asset_upload_is_image_checked_and_project_scoped(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    asset = covers.save_cover_asset(slug, "hero artwork.png", png_bytes((1800, 2700), "#432b20"))
    stored = storage.project_root(slug) / asset.relative_path

    assert stored.is_file()
    assert asset.width_px == 1800
    assert asset.height_px == 2700
    assert asset.relative_path.startswith("assets/covers/")
    with pytest.raises(ValueError, match="readable image"):
        covers.save_cover_asset(slug, "fake.png", b"not an image")


def test_cover_asset_preview_is_confined_to_project_cover_assets(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    asset = covers.save_cover_asset(slug, "preview.png", png_bytes((800, 1200), "#294663"))

    response = routes_cover.view_asset(slug, asset.relative_path)
    assert Path(response.path).resolve() == (storage.project_root(slug) / asset.relative_path).resolve()

    outside = storage.project_root(slug) / "project.json"
    assert outside.is_file()
    with pytest.raises(HTTPException) as exc:
        routes_cover.view_asset(slug, "project.json")
    assert exc.value.status_code == 404


def test_print_cover_export_produces_single_page_full_wrap_pdf(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    profile = CoverProfile(
        title="The Ember Cover",
        subtitle="A Test Novel",
        author="A. Writer",
        back_blurb="One city. One impossible promise. One last chance to survive the winter.",
        platform="kdp_paperback",
        trim_width=6,
        trim_height=9,
        page_count=300,
        paper_type="white_bw",
        spine_text="THE EMBER COVER · A. WRITER",
    )

    result = covers.export_cover(slug, profile)
    artifact = result.artifacts[0]
    path = storage.project_root(slug) / artifact.relative_path
    pdf = PdfReader(str(path))
    page = pdf.pages[0]

    assert artifact.format == "pdf"
    assert path.read_bytes()[:4] == b"%PDF"
    assert len(pdf.pages) == 1
    assert float(page.mediabox.width) / 72 == pytest.approx(result.geometry.cover_width, abs=0.01)
    assert float(page.mediabox.height) / 72 == pytest.approx(result.geometry.cover_height, abs=0.01)
    assert any(issue.code == "platform-proof-required" for issue in result.validation.issues)
    text = page.extract_text() or ""
    assert "The Ember Cover" in text
    assert "A. Writer" in text


def test_full_wrap_artwork_is_not_covered_by_panel_rectangles(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    asset = covers.save_cover_asset(slug, "wrap.png", png_bytes((3900, 2775), "#8f321e"))
    profile = CoverProfile(
        title="Visible Artwork",
        author="A. Writer",
        platform="kdp_paperback",
        trim_width=6,
        trim_height=9,
        page_count=300,
        artwork_path=asset.relative_path,
        artwork_mode="full_wrap",
        barcode_mode="none",
    )

    result = covers.export_cover(slug, profile)
    path = storage.project_root(slug) / result.artifacts[0].relative_path
    page = PdfReader(str(path)).pages[0]
    content = page.get_contents().get_data()

    image_operator = content.find(b" Do")
    assert image_operator >= 0
    assert content.rfind(b" re") < image_operator
    assert "/XObject" in str(page["/Resources"])


def test_kdp_ebook_export_builds_upload_jpeg_and_lossless_proof(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    profile = CoverProfile(
        title="Digital Ember",
        author="A. Writer",
        platform="kdp_ebook",
        ebook_width_px=625,
        ebook_height_px=1000,
    )

    validation = covers.validate_cover(slug, profile)
    result = covers.export_cover(slug, profile)
    root = storage.project_root(slug)

    assert validation.valid is True
    assert {artifact.format for artifact in result.artifacts} == {"jpg", "png"}
    for artifact in result.artifacts:
        path = root / artifact.relative_path
        assert path.is_file()
        with Image.open(path) as image:
            assert image.size == (625, 1000)
    assert any(issue.code == "ebook-ideal-size" for issue in validation.issues)


def test_ebook_artwork_opacity_is_applied_to_export(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    asset = covers.save_cover_asset(slug, "red.png", png_bytes((625, 1000), "#ff0000"))
    profile = CoverProfile(
        title="Opacity Test",
        platform="kdp_ebook",
        ebook_width_px=625,
        ebook_height_px=1000,
        background_color="#000000",
        artwork_path=asset.relative_path,
        artwork_opacity=0.5,
    )

    result = covers.export_cover(slug, profile)
    png_artifact = next(item for item in result.artifacts if item.format == "png")
    with Image.open(storage.project_root(slug) / png_artifact.relative_path) as image:
        red, green, blue = image.getpixel((20, 500))[:3]

    assert 120 <= red <= 135
    assert green == 0
    assert blue == 0
