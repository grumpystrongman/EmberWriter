from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from .cover_models import CoverProfile
from .release_models import (
    ReleaseArtifact,
    ReleaseBuildResponse,
    ReleaseEdition,
    ReleaseManifestFile,
    ReleasePackageArtifact,
    ReleaseProfile,
    ReleaseValidationIssue,
    ReleaseValidationResponse,
    RetailerTarget,
)
from .storage import project_root

KDP_METADATA_URL = "https://kdp.amazon.com/en_US/help/topic/G201097560"
KDP_KEYWORDS_URL = "https://kdp.amazon.com/en_US/help/topic/G201743260"
INGRAM_ISBN_URL = "https://www.ingramspark.com/free-isbns"
INGRAM_FILE_URL = "https://www.ingramspark.com/blog/file-requirements-for-print-books"
APPLE_PUBLISH_URL = "https://authors.apple.com/support/4574-publish-book-from-web"
APPLE_PRODUCT_PAGE_URL = "https://authors.apple.com/support/3969-craft-great-product-page-apple-books"
KOBO_METADATA_URL = "https://kobowritinglife.zendesk.com/hc/en-us/articles/360058975792-Metadata-Guidelines"
KOBO_ISBN_URL = "https://kobowritinglife.zendesk.com/hc/en-us/articles/360059386031-ISBNs-and-Kobo-Writing-Life"
RULES_REVIEWED = "2026-09-10"

_ALLOWED_RELEASE_SUFFIXES = {".epub", ".pdf", ".docx", ".jpg", ".jpeg", ".png", ".tif", ".tiff"}
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
_HTML_TAG = re.compile(r"<[^>]+>")
_URL_LIKE = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)


def _profile_path(slug: str) -> Path:
    return project_root(slug) / "publishing" / "release-profile.json"


def _cover_profile_path(slug: str) -> Path:
    return project_root(slug) / "publishing" / "cover-profile.json"


def _project_name(slug: str) -> str:
    path = project_root(slug) / "project.json"
    if not path.exists():
        raise FileNotFoundError(slug)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return str(payload.get("name") or slug)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_role(path: Path) -> str:
    name = path.name.casefold()
    suffix = path.suffix.casefold()
    if suffix == ".epub":
        return "ebook_interior"
    if suffix == ".docx":
        return "editorial"
    if suffix in _IMAGE_SUFFIXES or "full-wrap" in name or "cover" in name:
        return "cover"
    if suffix == ".pdf":
        return "print_interior"
    return "unknown"


def list_release_artifacts(slug: str) -> list[ReleaseArtifact]:
    root = project_root(slug)
    if not (root / "project.json").exists():
        raise FileNotFoundError(slug)
    export_root = root / "exports"
    if not export_root.exists():
        return []
    artifacts: list[ReleaseArtifact] = []
    for path in export_root.rglob("*"):
        if not path.is_file() or path.suffix.casefold() not in _ALLOWED_RELEASE_SUFFIXES:
            continue
        stat = path.stat()
        artifacts.append(
            ReleaseArtifact(
                relative_path=str(path.relative_to(root)).replace("\\", "/"),
                filename=path.name,
                suffix=path.suffix.casefold(),
                bytes=stat.st_size,
                sha256=_hash_file(path),
                role=_artifact_role(path),
                modified_at=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            )
        )
    return sorted(artifacts, key=lambda item: item.modified_at, reverse=True)


def _latest(artifacts: list[ReleaseArtifact], role: str, suffixes: set[str]) -> str:
    for artifact in artifacts:
        if artifact.role == role and artifact.suffix in suffixes:
            return artifact.relative_path
    return ""


def _saved_cover_profile(slug: str) -> CoverProfile | None:
    path = _cover_profile_path(slug)
    if not path.exists():
        return None
    try:
        return CoverProfile.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def default_release_profile(slug: str) -> ReleaseProfile:
    project_name = _project_name(slug)
    artifacts = list_release_artifacts(slug)
    cover = _saved_cover_profile(slug)
    title = cover.title if cover and cover.title.strip() else project_name
    author = cover.author if cover else ""
    subtitle = cover.subtitle if cover else ""
    imprint = cover.imprint if cover else ""
    ebook_cover = _latest(artifacts, "cover", {".jpg", ".jpeg", ".png", ".tif", ".tiff"})
    print_cover = _latest(artifacts, "cover", {".pdf"})
    ebook_interior = _latest(artifacts, "ebook_interior", {".epub"})
    print_interior = _latest(artifacts, "print_interior", {".pdf"})
    trim_width = cover.trim_width if cover else 6.0
    trim_height = cover.trim_height if cover else 9.0
    page_count = cover.page_count if cover else 300
    return ReleaseProfile(
        title=title,
        subtitle=subtitle,
        author=author,
        publisher=imprint or author,
        imprint=imprint,
        editions=[
            ReleaseEdition(
                id="ebook",
                format="ebook",
                retailers=["kdp", "apple_books", "kobo"],
                identifier_mode="none",
                price=0.0,
                interior_path=ebook_interior,
                cover_path=ebook_cover,
            ),
            ReleaseEdition(
                id="paperback",
                format="paperback",
                retailers=["kdp"],
                identifier_mode="retailer_assigned",
                price=0.0,
                interior_path=print_interior,
                cover_path=print_cover,
                trim_width=trim_width,
                trim_height=trim_height,
                page_count=page_count,
            ),
            ReleaseEdition(
                id="hardcover",
                format="hardcover",
                enabled=False,
                retailers=["ingramspark"],
                identifier_mode="own",
                price=0.0,
                trim_width=trim_width,
                trim_height=trim_height,
                page_count=page_count,
            ),
        ],
    )


def load_release_profile(slug: str) -> ReleaseProfile:
    path = _profile_path(slug)
    if not path.exists():
        return default_release_profile(slug)
    return ReleaseProfile.model_validate_json(path.read_text(encoding="utf-8"))


def save_release_profile(slug: str, profile: ReleaseProfile) -> ReleaseProfile:
    root = project_root(slug)
    if not (root / "project.json").exists():
        raise FileNotFoundError(slug)
    path = _profile_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(profile.model_dump(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return profile


def _safe_export_path(slug: str, relative_path: str) -> Path:
    root = project_root(slug)
    export_root = (root / "exports").resolve()
    candidate = (root / relative_path).resolve()
    if export_root not in candidate.parents:
        raise ValueError("Release files must come from the project's exports directory")
    if candidate.suffix.casefold() not in _ALLOWED_RELEASE_SUFFIXES:
        raise ValueError("Unsupported release artifact type")
    if not candidate.is_file():
        raise FileNotFoundError(relative_path)
    return candidate


def _isbn13(value: str) -> str:
    return re.sub(r"[^0-9]", "", value)


def _valid_isbn13(value: str) -> bool:
    digits = _isbn13(value)
    if len(digits) != 13:
        return False
    expected = (10 - sum((1 if index % 2 == 0 else 3) * int(digit) for index, digit in enumerate(digits[:12])) % 10) % 10
    return expected == int(digits[12])


def _valid_date(value: str) -> bool:
    if not value:
        return True
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _selected_retailers(profile: ReleaseProfile) -> list[RetailerTarget]:
    ordered: list[RetailerTarget] = []
    for edition in profile.editions:
        if not edition.enabled:
            continue
        for retailer in edition.retailers:
            if retailer not in ordered:
                ordered.append(retailer)
    return ordered


def validate_release(slug: str, profile: ReleaseProfile) -> ReleaseValidationResponse:
    issues: list[ReleaseValidationIssue] = []
    enabled = [edition for edition in profile.editions if edition.enabled]
    selected = _selected_retailers(profile)

    def add(
        level: str,
        code: str,
        message: str,
        *,
        retailer: RetailerTarget | None = None,
        edition_id: str | None = None,
        authority: str = "",
        authority_url: str = "",
    ) -> None:
        issues.append(
            ReleaseValidationIssue(
                level=level,
                code=code,
                message=message,
                retailer=retailer,
                edition_id=edition_id,
                authority=authority,
                authority_url=authority_url,
            )
        )

    if not profile.title.strip():
        add("error", "title-required", "A release title is required.")
    if not profile.author.strip():
        add("error", "author-required", "A primary author or pen name is required.")
    if not profile.description.strip():
        add("error", "description-required", "A public book description is required for release readiness.")
    if profile.series_number.strip() and not profile.series_name.strip():
        add("error", "series-name-required", "Series number requires a series name.")
    if profile.reading_age_min is not None and profile.reading_age_max is not None and profile.reading_age_min > profile.reading_age_max:
        add("error", "reading-age-order", "Minimum reading age cannot exceed maximum reading age.")
    for field_name, value in (
        ("publication date", profile.publication_date),
        ("release date", profile.release_date),
        ("original publication date", profile.original_publication_date),
    ):
        if not _valid_date(value):
            add("error", "invalid-date", f"{field_name.title()} must use YYYY-MM-DD.")
    if profile.rights_scope == "territories" and not [item for item in profile.territories if item.strip()]:
        add("error", "territories-required", "Choose at least one territory when rights are not worldwide.")
    if not enabled:
        add("error", "edition-required", "Enable at least one release edition.")

    edition_ids: set[str] = set()
    owned_isbns: dict[str, str] = {}
    for edition in enabled:
        if edition.id in edition_ids:
            add("error", "duplicate-edition-id", f"Edition id '{edition.id}' is duplicated.", edition_id=edition.id)
        edition_ids.add(edition.id)
        if not edition.retailers:
            add("error", "retailer-required", "Choose at least one retailer for this edition.", edition_id=edition.id)
        if not re.fullmatch(r"[A-Z]{3}", edition.currency.upper()):
            add("error", "currency-code", "Currency must be a three-letter code such as USD.", edition_id=edition.id)
        if edition.price == 0:
            add("warning", "price-review", "Price is zero. Confirm free-title eligibility or set the retailer list price before publication.", edition_id=edition.id)

        for role, relative_path in (("interior", edition.interior_path), ("cover", edition.cover_path)):
            if not relative_path:
                add("error", f"{role}-required", f"Select a generated {role} file for this edition.", edition_id=edition.id)
                continue
            try:
                path = _safe_export_path(slug, relative_path)
            except FileNotFoundError:
                add("error", f"{role}-missing", f"Selected {role} file no longer exists: {relative_path}", edition_id=edition.id)
                continue
            except ValueError as exc:
                add("error", f"{role}-invalid", str(exc), edition_id=edition.id)
                continue
            suffix = path.suffix.casefold()
            if role == "interior":
                expected = {".epub"} if edition.format == "ebook" else {".pdf"}
            else:
                expected = _IMAGE_SUFFIXES if edition.format == "ebook" else {".pdf"}
            if suffix not in expected:
                add(
                    "error",
                    f"{role}-format",
                    f"{edition.format.title()} {role} should use {', '.join(sorted(expected))}; selected {suffix}.",
                    edition_id=edition.id,
                )

        if edition.identifier_mode == "own":
            if not edition.isbn.strip():
                add("error", "isbn-required", "Owned-ISBN mode requires an ISBN-13.", edition_id=edition.id)
            elif not _valid_isbn13(edition.isbn):
                add("error", "isbn-invalid", "ISBN must be a valid ISBN-13 with a correct check digit.", edition_id=edition.id)
            else:
                normalized = _isbn13(edition.isbn)
                if normalized in owned_isbns:
                    add(
                        "error",
                        "isbn-reused",
                        f"ISBN {normalized} is already assigned to edition '{owned_isbns[normalized]}'. Each format/edition needs its own identifier.",
                        edition_id=edition.id,
                    )
                else:
                    owned_isbns[normalized] = edition.id
        elif edition.identifier_mode == "retailer_assigned" and len(edition.retailers) > 1:
            add(
                "error",
                "retailer-isbn-not-portable",
                "Retailer-assigned identifiers are not portable across multiple distributors. Use an owned ISBN or split the edition handoff.",
                edition_id=edition.id,
            )

        for retailer in edition.retailers:
            if retailer in {"apple_books", "kobo"} and edition.format != "ebook":
                add("error", "ebook-retailer-format", f"{retailer.replace('_', ' ').title()} handoff supports the eBook edition in Ember's current release workflow.", retailer=retailer, edition_id=edition.id)
            if retailer == "kdp":
                if edition.format in {"paperback", "hardcover"} and edition.identifier_mode == "none":
                    add("error", "kdp-print-isbn", "KDP print requires an ISBN unless the title qualifies for a specific exception; choose owned or retailer-assigned ISBN mode.", retailer="kdp", edition_id=edition.id, authority="Amazon KDP", authority_url=KDP_METADATA_URL)
                if edition.format == "ebook" and edition.cover_path:
                    suffix = Path(edition.cover_path).suffix.casefold()
                    if suffix not in {".jpg", ".jpeg", ".tif", ".tiff"}:
                        add("error", "kdp-ebook-cover-format", "KDP eBook cover handoff must use JPEG or TIFF.", retailer="kdp", edition_id=edition.id, authority="Amazon KDP", authority_url=KDP_METADATA_URL)
            elif retailer == "ingramspark":
                if edition.identifier_mode == "none":
                    add("error", "ingram-isbn", "IngramSpark distribution requires an ISBN for each distributed format.", retailer="ingramspark", edition_id=edition.id, authority="IngramSpark", authority_url=INGRAM_ISBN_URL)
                if edition.format != "ebook" and edition.page_count % 2:
                    add("error", "ingram-even-pages", "IngramSpark print page count must be even for manufacturing; confirm the final interior PDF page count.", retailer="ingramspark", edition_id=edition.id, authority="IngramSpark", authority_url=INGRAM_FILE_URL)

    if "kdp" in selected:
        if len([item for item in profile.keywords if item.strip()]) > 7:
            add("error", "kdp-keywords", "KDP currently allows up to seven keyword phrases.", retailer="kdp", authority="Amazon KDP", authority_url=KDP_KEYWORDS_URL)
        if len([item for item in profile.kdp_categories if item.strip()]) > 3:
            add("error", "kdp-categories-max", "KDP currently allows up to three categories during title setup.", retailer="kdp", authority="Amazon KDP", authority_url=KDP_METADATA_URL)
        if not [item for item in profile.kdp_categories if item.strip()]:
            add("warning", "kdp-categories", "Choose the most accurate current KDP categories in the publishing portal before release.", retailer="kdp", authority="Amazon KDP", authority_url=KDP_METADATA_URL)
        tagged = [profile.title, profile.subtitle, profile.author, *profile.keywords]
        if any(_HTML_TAG.search(value) for value in tagged if value):
            add("error", "kdp-html-metadata", "KDP title, subtitle, author, and keyword fields should not contain HTML tags.", retailer="kdp", authority="Amazon KDP", authority_url=KDP_METADATA_URL)

    if "apple_books" in selected:
        if not profile.description.strip():
            add("error", "apple-description", "Apple Books requires a Publisher Description.", retailer="apple_books", authority="Apple Books", authority_url=APPLE_PRODUCT_PAGE_URL)
        if not [item for item in profile.apple_categories if item.strip()]:
            add("error", "apple-category", "Apple Books requires at least one category.", retailer="apple_books", authority="Apple Books", authority_url=APPLE_PRODUCT_PAGE_URL)
        if not (profile.publisher.strip() or profile.author.strip()):
            add("error", "apple-publisher", "Enter a publisher name or self-publishing author name for Apple Books.", retailer="apple_books", authority="Apple Books", authority_url=APPLE_PUBLISH_URL)
        add("info", "apple-epubcheck", "Apple requires the submitted EPUB to pass the latest EPUBCheck. Ember packages the file but does not replace Apple's current validation portal.", retailer="apple_books", authority="Apple Books", authority_url=APPLE_PUBLISH_URL)

    if "kobo" in selected:
        if _URL_LIKE.search(profile.description) or any(_URL_LIKE.search(value) for value in (profile.title, profile.subtitle, profile.author) if value):
            add("error", "kobo-links", "Kobo does not allow website links/contact redirects in store metadata fields.", retailer="kobo", authority="Kobo Writing Life", authority_url=KOBO_METADATA_URL)
        for edition in enabled:
            if "kobo" in edition.retailers and edition.format == "ebook" and edition.identifier_mode == "none":
                add("info", "kobo-identifier", "Kobo can issue a Kobo-specific identifier, but some partner distribution destinations may require a valid ISBN.", retailer="kobo", edition_id=edition.id, authority="Kobo Writing Life", authority_url=KOBO_ISBN_URL)

    if "ingramspark" in selected and not ([item for item in profile.bisac_codes if item.strip()] or [item for item in profile.thema_codes if item.strip()]):
        add("warning", "ingram-subjects", "Add accurate BISAC and/or Thema subjects before Ingram distribution to improve retailer and library discoverability.", retailer="ingramspark", authority="IngramSpark", authority_url=INGRAM_ISBN_URL)

    cover = _saved_cover_profile(slug)
    if cover and any(edition.cover_path for edition in enabled):
        comparisons = (
            ("title", profile.title, cover.title),
            ("subtitle", profile.subtitle, cover.subtitle),
            ("author", profile.author, cover.author),
        )
        for label, metadata_value, cover_value in comparisons:
            if cover_value.strip() and metadata_value.strip().casefold() != cover_value.strip().casefold():
                add(
                    "error",
                    "cover-metadata-mismatch",
                    f"Release {label} does not match the saved Cover Studio {label}. Store metadata and cover text must agree.",
                    authority="Amazon KDP / Apple Books / Kobo Writing Life",
                    authority_url=KDP_METADATA_URL,
                )

    return ReleaseValidationResponse(
        valid=not any(issue.level == "error" for issue in issues),
        issues=issues,
        enabled_editions=len(enabled),
        selected_retailers=selected,
    )


def _retailer_payload(profile: ReleaseProfile, retailer: RetailerTarget) -> dict:
    editions = [
        {
            "id": edition.id,
            "format": edition.format,
            "identifier_mode": edition.identifier_mode,
            "isbn": _isbn13(edition.isbn) if edition.isbn else "",
            "price": edition.price,
            "currency": edition.currency.upper(),
            "interior_path": edition.interior_path,
            "cover_path": edition.cover_path,
            "trim_width": edition.trim_width if edition.format != "ebook" else None,
            "trim_height": edition.trim_height if edition.format != "ebook" else None,
            "page_count": edition.page_count if edition.format != "ebook" else None,
            "drm": edition.drm if edition.format == "ebook" else None,
            "expanded_distribution": edition.expanded_distribution if retailer == "kdp" and edition.format == "paperback" else None,
        }
        for edition in profile.editions
        if edition.enabled and retailer in edition.retailers
    ]
    payload = {
        "retailer": retailer,
        "rules_reviewed": RULES_REVIEWED,
        "title": profile.title,
        "subtitle": profile.subtitle,
        "series_name": profile.series_name,
        "series_number": profile.series_number,
        "author": profile.author,
        "contributors": [item.model_dump() for item in profile.contributors],
        "publisher": profile.publisher,
        "imprint": profile.imprint,
        "description": profile.description,
        "short_description": profile.short_description,
        "author_bio": profile.author_bio,
        "language": profile.language,
        "publication_date": profile.publication_date,
        "release_date": profile.release_date,
        "original_publication_date": profile.original_publication_date,
        "explicit_content": profile.explicit_content,
        "public_domain": profile.public_domain,
        "reading_age_min": profile.reading_age_min,
        "reading_age_max": profile.reading_age_max,
        "rights_scope": profile.rights_scope,
        "territories": profile.territories,
        "editions": editions,
    }
    if retailer == "kdp":
        payload.update(keywords=profile.keywords[:7], categories=profile.kdp_categories[:3], authority_url=KDP_METADATA_URL)
    elif retailer == "ingramspark":
        payload.update(keywords=profile.keywords, bisac_codes=profile.bisac_codes, thema_codes=profile.thema_codes, authority_url=INGRAM_ISBN_URL)
    elif retailer == "apple_books":
        payload.update(categories=profile.apple_categories, authority_url=APPLE_PUBLISH_URL)
    elif retailer == "kobo":
        payload.update(categories=profile.kobo_categories, keywords=profile.keywords, authority_url=KOBO_METADATA_URL)
    else:
        payload.update(keywords=profile.keywords, bisac_codes=profile.bisac_codes, thema_codes=profile.thema_codes, authority_url="")
    return payload


def _metadata_csv(profile: ReleaseProfile) -> str:
    buffer = io.StringIO()
    fieldnames = [
        "retailer",
        "edition_id",
        "format",
        "title",
        "subtitle",
        "series_name",
        "series_number",
        "author",
        "publisher",
        "imprint",
        "language",
        "identifier_mode",
        "isbn",
        "price",
        "currency",
        "release_date",
        "rights_scope",
        "territories",
        "keywords",
        "categories",
        "interior_path",
        "cover_path",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for edition in profile.editions:
        if not edition.enabled:
            continue
        for retailer in edition.retailers:
            if retailer == "kdp":
                categories = profile.kdp_categories
            elif retailer == "apple_books":
                categories = profile.apple_categories
            elif retailer == "kobo":
                categories = profile.kobo_categories
            else:
                categories = [*profile.bisac_codes, *profile.thema_codes]
            writer.writerow(
                {
                    "retailer": retailer,
                    "edition_id": edition.id,
                    "format": edition.format,
                    "title": profile.title,
                    "subtitle": profile.subtitle,
                    "series_name": profile.series_name,
                    "series_number": profile.series_number,
                    "author": profile.author,
                    "publisher": profile.publisher,
                    "imprint": profile.imprint,
                    "language": profile.language,
                    "identifier_mode": edition.identifier_mode,
                    "isbn": _isbn13(edition.isbn) if edition.isbn else "",
                    "price": edition.price,
                    "currency": edition.currency.upper(),
                    "release_date": profile.release_date,
                    "rights_scope": profile.rights_scope,
                    "territories": " | ".join(profile.territories),
                    "keywords": " | ".join(profile.keywords),
                    "categories": " | ".join(categories),
                    "interior_path": edition.interior_path,
                    "cover_path": edition.cover_path,
                }
            )
    return buffer.getvalue()


def build_release_package(slug: str, profile: ReleaseProfile) -> ReleaseBuildResponse:
    validation = validate_release(slug, profile)
    if not validation.valid:
        messages = "; ".join(issue.message for issue in validation.issues if issue.level == "error")
        raise ValueError(messages or "Release profile is not ready")
    save_release_profile(slug, profile)

    release_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-release-" + uuid4().hex[:8]
    root = project_root(slug)
    directory = root / "exports" / release_id
    directory.mkdir(parents=True, exist_ok=True)
    manifest_files: list[ReleaseManifestFile] = []
    packaged_sources: list[tuple[Path, str]] = []

    for edition in profile.editions:
        if not edition.enabled:
            continue
        safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", edition.id).strip("-.") or "edition"
        for role, relative in (("interior", edition.interior_path), ("cover", edition.cover_path)):
            source = _safe_export_path(slug, relative)
            package_path = f"files/{safe_id}/{role}{source.suffix.casefold()}"
            digest = _hash_file(source)
            manifest_files.append(
                ReleaseManifestFile(
                    edition_id=edition.id,
                    role=role,
                    source_path=relative,
                    package_path=package_path,
                    bytes=source.stat().st_size,
                    sha256=digest,
                )
            )
            packaged_sources.append((source, package_path))

    manifest = {
        "schema_version": 1,
        "release_id": release_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "title": profile.title,
        "rules_reviewed": RULES_REVIEWED,
        "retailers": validation.selected_retailers,
        "files": [item.model_dump() for item in manifest_files],
    }
    metadata_path = directory / "release-profile.json"
    manifest_path = directory / "release-manifest.json"
    csv_path = directory / "retailer-metadata.csv"
    metadata_path.write_text(json.dumps(profile.model_dump(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    csv_path.write_text(_metadata_csv(profile), encoding="utf-8", newline="")

    zip_path = directory / "release-package.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("metadata/release-profile.json", metadata_path.read_bytes())
        archive.writestr("metadata/release-manifest.json", manifest_path.read_bytes())
        archive.writestr("metadata/retailer-metadata.csv", csv_path.read_bytes())
        for retailer in validation.selected_retailers:
            archive.writestr(
                f"retailers/{retailer}.json",
                json.dumps(_retailer_payload(profile, retailer), indent=2, ensure_ascii=False) + "\n",
            )
        archive.writestr(
            "README.txt",
            "EmberWriter release handoff\n\n"
            f"Release: {release_id}\n"
            f"Rules reviewed: {RULES_REVIEWED}\n\n"
            "This package does not auto-publish or claim distributor approval. Re-open the selected files, verify metadata, then use each retailer's current portal and preview/preflight before publication.\n"
            "Retailer rules change; the authority URLs in each retailer JSON are the final reference.\n",
        )
        for source, package_path in packaged_sources:
            archive.write(source, package_path)

    artifacts = []
    for fmt, path in (("zip", zip_path), ("json", manifest_path), ("csv", csv_path)):
        artifacts.append(
            ReleasePackageArtifact(
                format=fmt,
                filename=path.name,
                relative_path=str(path.relative_to(root)).replace("\\", "/"),
                bytes=path.stat().st_size,
            )
        )
    return ReleaseBuildResponse(
        release_id=release_id,
        validation=validation,
        manifest_files=manifest_files,
        artifacts=artifacts,
    )
