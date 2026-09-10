from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from app import distribution, storage
from app.release_models import ReleaseEdition, ReleaseProfile


def use_temp_data(tmp_path: Path) -> str:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"
    return storage.create_project("Release Test")["slug"]


def write_epub(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", "<container />")
        archive.writestr("OEBPS/content.opf", "<package />")


def write_pdf(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=LETTER)
    pdf.drawString(72, 720, "Release test")
    pdf.save()


def write_jpg(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1600, 2560), "#3a2118")
    image.save(path, format="JPEG", quality=90)


def make_ebook_files(slug: str) -> tuple[str, str]:
    root = storage.project_root(slug)
    interior = root / "exports" / "ebook-build" / "release-test.epub"
    cover = root / "exports" / "cover-build" / "release-test-ebook.jpg"
    write_epub(interior)
    write_jpg(cover)
    return (
        str(interior.relative_to(root)).replace("\\", "/"),
        str(cover.relative_to(root)).replace("\\", "/"),
    )


def make_print_files(slug: str) -> tuple[str, str]:
    root = storage.project_root(slug)
    interior = root / "exports" / "print-build" / "release-test.pdf"
    cover = root / "exports" / "cover-build" / "release-test-full-wrap.pdf"
    write_pdf(interior)
    write_pdf(cover)
    return (
        str(interior.relative_to(root)).replace("\\", "/"),
        str(cover.relative_to(root)).replace("\\", "/"),
    )


def test_release_artifact_inventory_classifies_generated_files(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    epub_path, jpg_path = make_ebook_files(slug)
    print_path, cover_pdf = make_print_files(slug)

    artifacts = distribution.list_release_artifacts(slug)
    by_path = {item.relative_path: item for item in artifacts}

    assert by_path[epub_path].role == "ebook_interior"
    assert by_path[jpg_path].role == "cover"
    assert by_path[print_path].role == "print_interior"
    assert by_path[cover_pdf].role == "cover"
    assert len(by_path[epub_path].sha256) == 64


def test_kdp_metadata_limits_and_print_identifier_rules_are_enforced(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    interior, cover = make_print_files(slug)
    profile = ReleaseProfile(
        title="A Release",
        author="A. Writer",
        description="A complete description.",
        keywords=[f"keyword {index}" for index in range(8)],
        kdp_categories=["Fiction A", "Fiction B", "Fiction C", "Fiction D"],
        editions=[
            ReleaseEdition(
                id="paperback",
                format="paperback",
                retailers=["kdp"],
                identifier_mode="none",
                price=14.99,
                interior_path=interior,
                cover_path=cover,
            )
        ],
    )

    result = distribution.validate_release(slug, profile)
    codes = {issue.code for issue in result.issues}

    assert result.valid is False
    assert "kdp-keywords" in codes
    assert "kdp-categories-max" in codes
    assert "kdp-print-isbn" in codes


def test_retailer_assigned_identifier_cannot_span_distributors(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    interior, cover = make_print_files(slug)
    profile = ReleaseProfile(
        title="Shared Print",
        author="A. Writer",
        description="A complete description.",
        bisac_codes=["FIC009000"],
        editions=[
            ReleaseEdition(
                id="paperback",
                format="paperback",
                retailers=["kdp", "ingramspark"],
                identifier_mode="retailer_assigned",
                price=16.99,
                interior_path=interior,
                cover_path=cover,
                page_count=300,
            )
        ],
    )

    result = distribution.validate_release(slug, profile)

    assert result.valid is False
    assert any(issue.code == "retailer-isbn-not-portable" for issue in result.issues)


def test_apple_and_kobo_store_metadata_rules_are_surfaced(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    interior, cover = make_ebook_files(slug)
    profile = ReleaseProfile(
        title="Digital Release",
        author="A. Writer",
        publisher="A. Writer",
        description="Read more at https://example.com",
        apple_categories=[],
        editions=[
            ReleaseEdition(
                id="ebook",
                format="ebook",
                retailers=["apple_books", "kobo"],
                identifier_mode="none",
                price=4.99,
                interior_path=interior,
                cover_path=cover,
            )
        ],
    )

    result = distribution.validate_release(slug, profile)
    codes = {issue.code for issue in result.issues}

    assert result.valid is False
    assert "apple-category" in codes
    assert "kobo-links" in codes
    assert "apple-epubcheck" in codes
    assert "kobo-identifier" in codes


def test_ingram_requires_valid_unique_isbn_and_even_print_pages(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    interior, cover = make_print_files(slug)
    invalid = ReleaseProfile(
        title="Ingram Release",
        author="A. Writer",
        description="A complete description.",
        bisac_codes=["FIC009000"],
        editions=[
            ReleaseEdition(
                id="paperback",
                format="paperback",
                retailers=["ingramspark"],
                identifier_mode="own",
                isbn="9780306406157",
                price=16.99,
                interior_path=interior,
                cover_path=cover,
                page_count=301,
            )
        ],
    )
    valid = invalid.model_copy(
        update={
            "editions": [invalid.editions[0].model_copy(update={"page_count": 300})],
        }
    )

    invalid_result = distribution.validate_release(slug, invalid)
    valid_result = distribution.validate_release(slug, valid)

    assert invalid_result.valid is False
    assert any(issue.code == "ingram-even-pages" for issue in invalid_result.issues)
    assert valid_result.valid is True


def test_release_package_contains_selected_files_metadata_and_hash_manifest(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    interior, cover = make_ebook_files(slug)
    profile = ReleaseProfile(
        title="Packaged Ember",
        subtitle="A Release Test",
        author="A. Writer",
        publisher="A. Writer",
        description="A dangerous secret changes everything.",
        keywords=["dark fantasy", "found family"],
        kdp_categories=["Fiction > Fantasy"],
        editions=[
            ReleaseEdition(
                id="ebook",
                format="ebook",
                retailers=["kdp"],
                identifier_mode="none",
                price=4.99,
                interior_path=interior,
                cover_path=cover,
            )
        ],
    )

    result = distribution.build_release_package(slug, profile)
    root = storage.project_root(slug)
    by_format = {artifact.format: root / artifact.relative_path for artifact in result.artifacts}

    assert result.validation.valid is True
    assert len(result.manifest_files) == 2
    assert by_format["zip"].is_file()
    assert by_format["json"].is_file()
    assert by_format["csv"].is_file()

    manifest = json.loads(by_format["json"].read_text(encoding="utf-8"))
    assert manifest["release_id"] == result.release_id
    assert {item["role"] for item in manifest["files"]} == {"interior", "cover"}
    assert all(len(item["sha256"]) == 64 for item in manifest["files"])

    with zipfile.ZipFile(by_format["zip"]) as archive:
        names = set(archive.namelist())
        assert "metadata/release-profile.json" in names
        assert "metadata/release-manifest.json" in names
        assert "metadata/retailer-metadata.csv" in names
        assert "retailers/kdp.json" in names
        assert "files/ebook/interior.epub" in names
        assert "files/ebook/cover.jpg" in names
        retailer = json.loads(archive.read("retailers/kdp.json"))
        assert retailer["title"] == "Packaged Ember"
        assert retailer["keywords"] == ["dark fantasy", "found family"]


def test_release_paths_cannot_escape_exports_directory(tmp_path: Path) -> None:
    slug = use_temp_data(tmp_path)
    root = storage.project_root(slug)
    outside = root / "manuscript" / "chapter-001.md"

    profile = ReleaseProfile(
        title="Unsafe Release",
        author="A. Writer",
        description="A complete description.",
        kdp_categories=["Fiction"],
        editions=[
            ReleaseEdition(
                id="ebook",
                format="ebook",
                retailers=["kdp"],
                price=4.99,
                interior_path=str(outside.relative_to(root)).replace("\\", "/"),
                cover_path=str(outside.relative_to(root)).replace("\\", "/"),
            )
        ],
    )

    result = distribution.validate_release(slug, profile)

    assert result.valid is False
    assert any(issue.code.endswith("-invalid") for issue in result.issues)
