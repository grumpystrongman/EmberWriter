from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageColor
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .cover_models import (
    CoverAsset,
    CoverExportResponse,
    CoverGeometry,
    CoverProfile,
    CoverValidationIssue,
    CoverValidationResponse,
)
from .storage import project_root

KDP_PAPERBACK_URL = "https://kdp.amazon.com/en_US/help/topic/G201953020"
KDP_EBOOK_URL = "https://kdp.amazon.com/en_US/help/topic/G200645690"
INGRAM_TEMPLATE_URL = "https://myaccount.ingramspark.com/Portal/Tools/CoverTemplateGenerator"

KDP_SPINE_FACTORS = {
    "white_bw": 0.002252,
    "cream_bw": 0.0025,
    "premium_color": 0.002347,
    "standard_color": 0.002252,
}

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp"}


def _profile_path(slug: str) -> Path:
    return project_root(slug) / "publishing" / "cover-profile.json"


def _project_name(slug: str) -> str:
    root = project_root(slug)
    metadata_path = root / "project.json"
    if not metadata_path.exists():
        raise FileNotFoundError(slug)
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return slug
    return str(payload.get("name") or slug)


def default_cover_profile(slug: str) -> CoverProfile:
    return CoverProfile(title=_project_name(slug))


def load_cover_profile(slug: str) -> CoverProfile:
    path = _profile_path(slug)
    if not path.exists():
        return default_cover_profile(slug)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return CoverProfile.model_validate(payload)


def save_cover_profile(slug: str, profile: CoverProfile) -> CoverProfile:
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


def cover_geometry(profile: CoverProfile) -> CoverGeometry:
    if profile.platform == "kdp_ebook":
        return CoverGeometry(
            platform=profile.platform,
            trim_width=profile.trim_width,
            trim_height=profile.trim_height,
            page_count=profile.page_count,
            bleed=0.0,
            spine_width=0.0,
            cover_width=profile.ebook_width_px / 300.0,
            cover_height=profile.ebook_height_px / 300.0,
            back_x=0.0,
            spine_x=0.0,
            front_x=0.0,
            safe_inset=0.0,
            spine_safe_inset=0.0,
            spine_text_allowed=False,
            exact_platform_formula=True,
            authority="Amazon Kindle Direct Publishing",
            authority_url=KDP_EBOOK_URL,
            notes=[
                "Pixel dimensions are authoritative for eBook output; inch dimensions are only a 300-PPI design equivalent.",
                "KDP currently identifies 1600 × 2560 px as the ideal cover dimensions and requires JPEG or TIFF upload.",
            ],
        )

    if profile.platform == "kdp_paperback":
        bleed = 0.125
        spine = profile.page_count * KDP_SPINE_FACTORS[profile.paper_type]
        authority = "Amazon Kindle Direct Publishing"
        authority_url = KDP_PAPERBACK_URL
        exact = True
        notes = [
            "KDP paperback wrap uses back + spine + front with 0.125 in bleed on the outside edges.",
            "Spine text is treated as allowed at 80 pages or more, matching KDP's conservative rejection guidance.",
        ]
        safe_inset = max(0.125, profile.safe_inset)
        spine_safe = max(0.0625, profile.spine_safe_inset)
    elif profile.platform == "ingramspark":
        if profile.manual_spine_width <= 0:
            spine = 0.0
        else:
            spine = profile.manual_spine_width
        bleed = 0.125
        authority = "IngramSpark"
        authority_url = INGRAM_TEMPLATE_URL
        exact = False
        notes = [
            "IngramSpark geometry depends on the selected print product. Use the official template generator and enter its spine width here.",
            "Ember does not invent a universal Ingram spine formula; the supplied template measurement remains authoritative.",
        ]
        safe_inset = max(0.25, profile.safe_inset)
        spine_safe = max(0.03125 if spine < 0.35 else 0.0625, profile.spine_safe_inset)
    else:
        spine = profile.manual_spine_width
        bleed = profile.bleed
        authority = "Custom print specification"
        authority_url = ""
        exact = False
        notes = ["Custom geometry uses the author/publisher supplied bleed and spine measurements."]
        safe_inset = profile.safe_inset
        spine_safe = profile.spine_safe_inset

    cover_width = bleed + profile.trim_width + spine + profile.trim_width + bleed
    cover_height = bleed + profile.trim_height + bleed
    back_x = bleed
    spine_x = bleed + profile.trim_width
    front_x = spine_x + spine
    return CoverGeometry(
        platform=profile.platform,
        trim_width=profile.trim_width,
        trim_height=profile.trim_height,
        page_count=profile.page_count,
        bleed=bleed,
        spine_width=round(spine, 6),
        cover_width=round(cover_width, 6),
        cover_height=round(cover_height, 6),
        back_x=round(back_x, 6),
        spine_x=round(spine_x, 6),
        front_x=round(front_x, 6),
        safe_inset=round(safe_inset, 6),
        spine_safe_inset=round(spine_safe, 6),
        spine_text_allowed=profile.page_count >= 80 and spine > 0.125,
        exact_platform_formula=exact,
        authority=authority,
        authority_url=authority_url,
        notes=notes,
    )


def _asset_path(slug: str, relative_path: str) -> Path:
    root = project_root(slug)
    candidate = (root / relative_path).resolve()
    asset_root = (root / "assets" / "covers").resolve()
    if asset_root not in candidate.parents or candidate.suffix.casefold() not in _IMAGE_SUFFIXES:
        raise ValueError("Cover asset must live under assets/covers and use a supported image format")
    return candidate


def save_cover_asset(slug: str, filename: str, data: bytes) -> CoverAsset:
    if not data:
        raise ValueError("Cover image is empty")
    suffix = Path(filename).suffix.casefold()
    if suffix not in _IMAGE_SUFFIXES:
        raise ValueError("Cover artwork must be PNG, JPEG, TIFF, or WebP")
    if len(data) > 100 * 1024 * 1024:
        raise ValueError("Cover artwork exceeds the 100 MB upload limit")
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (OSError, ValueError) as exc:
        raise ValueError("Cover artwork is not a readable image") from exc
    width, height = image.size
    if width < 64 or height < 64:
        raise ValueError("Cover artwork is too small")
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(filename).name).strip("-.") or f"cover{suffix}"
    digest = hashlib.sha256(data).hexdigest()[:10]
    relative = f"assets/covers/{digest}-{safe_name}"
    path = _asset_path(slug, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return CoverAsset(
        relative_path=relative,
        filename=path.name,
        width_px=width,
        height_px=height,
        format=(image.format or suffix.lstrip(".")).upper(),
        bytes=len(data),
    )


def _image_info(slug: str, relative_path: str) -> tuple[int, int] | None:
    if not relative_path:
        return None
    path = _asset_path(slug, relative_path)
    if not path.exists():
        return None
    try:
        with Image.open(path) as image:
            return image.size
    except OSError:
        return None


def validate_cover(slug: str, profile: CoverProfile) -> CoverValidationResponse:
    geometry = cover_geometry(profile)
    issues: list[CoverValidationIssue] = []

    def add(level: str, code: str, message: str) -> None:
        issues.append(CoverValidationIssue(level=level, code=code, message=message))

    if not profile.title.strip():
        add("error", "title-required", "A cover title is required.")

    if profile.platform == "kdp_paperback":
        if not 24 <= profile.page_count <= 830:
            add("error", "kdp-page-count", "KDP paperback page count must be between 24 and 830 for this calculator mode.")
        if profile.bleed != 0.125:
            add("info", "kdp-bleed-fixed", "KDP paperback export uses the current required 0.125 in cover bleed regardless of the custom bleed field.")
        if profile.spine_text.strip() and not geometry.spine_text_allowed:
            add("error", "spine-text-page-count", "Remove spine text or increase the final formatted page count to at least 80 pages.")
    elif profile.platform == "ingramspark":
        if profile.manual_spine_width <= 0:
            add("error", "ingram-template-spine", "Generate an IngramSpark cover template for the exact print product and enter its spine width before export.")
        if profile.safe_inset < 0.25:
            add("info", "ingram-type-safety", "Ember increases the preview/export type-safe inset to IngramSpark's 0.25 in recommended minimum.")
    elif profile.platform == "custom_print" and profile.manual_spine_width <= 0:
        add("warning", "custom-zero-spine", "Custom print cover has zero spine width. Confirm that this is intentional.")

    if profile.platform == "kdp_ebook":
        ratio = profile.ebook_height_px / profile.ebook_width_px
        if profile.ebook_height_px < 1000 or profile.ebook_width_px < 625:
            add("error", "ebook-minimum-size", "KDP eBook covers must be at least 625 × 1000 pixels.")
        if profile.ebook_height_px > 10000 or profile.ebook_width_px > 10000:
            add("error", "ebook-maximum-size", "KDP eBook cover dimensions cannot exceed 10,000 pixels.")
        if ratio < 1.6:
            add("warning", "ebook-ratio", "KDP recommends an eBook cover height/width ratio of at least 1.6:1.")
        if (profile.ebook_width_px, profile.ebook_height_px) != (1600, 2560):
            add("info", "ebook-ideal-size", "KDP currently identifies 1600 × 2560 pixels as its ideal eBook cover dimensions.")
    else:
        add(
            "info",
            "platform-proof-required",
            "Geometry checks are not distributor approval. Run the exported cover through the target platform preview/preflight before publishing to verify fonts, transparency, color, and final placement.",
        )

    artwork = _image_info(slug, profile.artwork_path) if profile.artwork_path else None
    if profile.artwork_path and artwork is None:
        add("error", "artwork-missing", "The configured cover artwork file is missing or unreadable.")
    elif artwork:
        width, height = artwork
        if profile.platform == "kdp_ebook":
            if width < profile.ebook_width_px or height < profile.ebook_height_px:
                add("warning", "artwork-upscale", f"Artwork is {width} × {height}px and will be upscaled for the selected eBook canvas.")
        else:
            target_width = geometry.cover_width if profile.artwork_mode == "full_wrap" else profile.trim_width + geometry.bleed
            target_height = geometry.cover_height
            effective_dpi = min(width / target_width, height / target_height)
            if effective_dpi < 300:
                add("warning", "artwork-low-resolution", f"Artwork resolves to about {effective_dpi:.0f} PPI at placement size; print artwork should be at least 300 PPI.")

    if len(profile.back_blurb) > 2600:
        add("warning", "blurb-density", "The back-cover blurb is long for the available cover area; check the exported proof for crowding.")
    if profile.barcode_mode == "custom" and not profile.barcode_path:
        add("error", "barcode-image-required", "Custom barcode mode requires an uploaded barcode image.")
    if profile.barcode_path and _image_info(slug, profile.barcode_path) is None:
        add("error", "barcode-missing", "The configured barcode image is missing or unreadable.")

    return CoverValidationResponse(
        valid=not any(issue.level == "error" for issue in issues),
        geometry=geometry,
        issues=issues,
    )


def _color(value: str, fallback: str) -> tuple[float, float, float]:
    try:
        rgb = ImageColor.getrgb(value)
    except ValueError:
        rgb = ImageColor.getrgb(fallback)
    return tuple(channel / 255.0 for channel in rgb[:3])


def _font_name(family: str, *, bold: bool = False, italic: bool = False) -> str:
    mapping = {
        ("Helvetica", False, False): "Helvetica",
        ("Helvetica", True, False): "Helvetica-Bold",
        ("Helvetica", False, True): "Helvetica-Oblique",
        ("Helvetica", True, True): "Helvetica-BoldOblique",
        ("Times", False, False): "Times-Roman",
        ("Times", True, False): "Times-Bold",
        ("Times", False, True): "Times-Italic",
        ("Times", True, True): "Times-BoldItalic",
        ("Courier", False, False): "Courier",
        ("Courier", True, False): "Courier-Bold",
        ("Courier", False, True): "Courier-Oblique",
        ("Courier", True, True): "Courier-BoldOblique",
    }
    return mapping[(family, bold, italic)]


def _wrap(text: str, font: str, size: float, width_points: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [text]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if stringWidth(candidate, font, size) <= width_points:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def _draw_text_block(
    pdf: canvas.Canvas,
    text: str,
    *,
    x: float,
    y_top: float,
    width: float,
    font: str,
    size: float,
    color: tuple[float, float, float],
    align: str,
    leading: float | None = None,
    max_lines: int | None = None,
) -> float:
    if not text.strip():
        return y_top
    leading = leading or size * 1.22
    lines = _wrap(text.strip(), font, size, width)
    if max_lines is not None:
        lines = lines[:max_lines]
    pdf.setFillColorRGB(*color)
    pdf.setFont(font, size)
    y = y_top
    for line in lines:
        if align == "center":
            pdf.drawCentredString(x + width / 2, y, line)
        elif align == "right":
            pdf.drawRightString(x + width, y, line)
        else:
            pdf.drawString(x, y, line)
        y -= leading
    return y


def _cover_artwork(slug: str, relative_path: str, width_px: int, height_px: int) -> ImageReader:
    path = _asset_path(slug, relative_path)
    if not path.exists():
        raise FileNotFoundError(relative_path)
    with Image.open(path) as source:
        image = source.convert("RGB")
        source_ratio = image.width / image.height
        target_ratio = width_px / height_px
        if source_ratio > target_ratio:
            new_width = max(1, round(image.height * target_ratio))
            left = max(0, (image.width - new_width) // 2)
            image = image.crop((left, 0, left + new_width, image.height))
        else:
            new_height = max(1, round(image.width / target_ratio))
            top = max(0, (image.height - new_height) // 2)
            image = image.crop((0, top, image.width, top + new_height))
        image = image.resize((width_px, height_px), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=94, optimize=True)
    buffer.seek(0)
    return ImageReader(buffer)


def _draw_barcode_area(pdf: canvas.Canvas, slug: str, profile: CoverProfile, geometry: CoverGeometry) -> None:
    if profile.barcode_mode == "none" or profile.platform == "kdp_ebook":
        return
    width = min(profile.barcode_width, profile.trim_width - 0.5) * inch
    height = min(profile.barcode_height, profile.trim_height - 0.5) * inch
    margin = max(profile.barcode_margin, geometry.safe_inset) * inch
    x = (geometry.back_x + profile.trim_width) * inch - margin - width
    y = (geometry.bleed + geometry.safe_inset) * inch
    pdf.setFillColorRGB(1, 1, 1)
    pdf.rect(x, y, width, height, fill=1, stroke=0)
    if profile.barcode_mode == "custom" and profile.barcode_path:
        path = _asset_path(slug, profile.barcode_path)
        if path.exists():
            pdf.drawImage(str(path), x + 4, y + 4, width=width - 8, height=height - 8, preserveAspectRatio=True, anchor="c", mask="auto")


def _render_print_pdf(slug: str, profile: CoverProfile, geometry: CoverGeometry, path: Path) -> None:
    page_width = geometry.cover_width * inch
    page_height = geometry.cover_height * inch
    pdf = canvas.Canvas(str(path), pagesize=(page_width, page_height), pageCompression=1)
    pdf.setTitle(profile.title)
    pdf.setAuthor(profile.author)

    pdf.setFillColorRGB(*_color(profile.background_color, "#15100d"))
    pdf.rect(0, 0, page_width, page_height, fill=1, stroke=0)

    if profile.artwork_path:
        if profile.artwork_mode == "full_wrap":
            art = _cover_artwork(slug, profile.artwork_path, max(1, round(geometry.cover_width * 300)), max(1, round(geometry.cover_height * 300)))
            pdf.drawImage(art, 0, 0, width=page_width, height=page_height, mask="auto")
        else:
            art_width = profile.trim_width + geometry.bleed
            art = _cover_artwork(slug, profile.artwork_path, max(1, round(art_width * 300)), max(1, round(geometry.cover_height * 300)))
            pdf.drawImage(art, geometry.front_x * inch, 0, width=art_width * inch, height=page_height, mask="auto")

    pdf.setFillColorRGB(*_color(profile.back_overlay_color, "#18110e"))
    pdf.rect(geometry.back_x * inch, geometry.bleed * inch, profile.trim_width * inch, profile.trim_height * inch, fill=1, stroke=0)
    if not (profile.artwork_path and profile.artwork_mode == "front"):
        pdf.setFillColorRGB(*_color(profile.front_overlay_color, "#1c1410"))
        pdf.rect(geometry.front_x * inch, geometry.bleed * inch, profile.trim_width * inch, profile.trim_height * inch, fill=1, stroke=0)
    if geometry.spine_width > 0:
        pdf.setFillColorRGB(*_color(profile.spine_color, "#25170f"))
        pdf.rect(geometry.spine_x * inch, geometry.bleed * inch, geometry.spine_width * inch, profile.trim_height * inch, fill=1, stroke=0)

    safe = geometry.safe_inset
    front_x = (geometry.front_x + safe) * inch
    front_width = (profile.trim_width - safe * 2) * inch
    top = (geometry.bleed + profile.trim_height - safe) * inch
    title_font = _font_name(profile.title_font, bold=True)
    subtitle_font = _font_name(profile.title_font, italic=True)
    author_font = _font_name(profile.title_font, bold=True)
    _draw_text_block(
        pdf,
        profile.title,
        x=front_x,
        y_top=top - 0.55 * inch,
        width=front_width,
        font=title_font,
        size=profile.title_size,
        color=_color(profile.title_color, "#f3e7da"),
        align=profile.title_align,
        max_lines=5,
    )
    _draw_text_block(
        pdf,
        profile.subtitle,
        x=front_x,
        y_top=top - 2.0 * inch,
        width=front_width,
        font=subtitle_font,
        size=profile.subtitle_size,
        color=_color(profile.subtitle_color, "#d7b99f"),
        align=profile.title_align,
        max_lines=5,
    )
    _draw_text_block(
        pdf,
        profile.author,
        x=front_x,
        y_top=(geometry.bleed + safe + 0.65) * inch,
        width=front_width,
        font=author_font,
        size=profile.author_size,
        color=_color(profile.author_color, "#f0d5bf"),
        align=profile.title_align,
        max_lines=3,
    )

    back_x = (geometry.back_x + safe) * inch
    back_width = (profile.trim_width - safe * 2) * inch
    back_top = (geometry.bleed + profile.trim_height - safe - 0.35) * inch
    body_font = _font_name(profile.body_font)
    _draw_text_block(
        pdf,
        profile.back_blurb,
        x=back_x,
        y_top=back_top,
        width=back_width,
        font=body_font,
        size=profile.body_size,
        color=_color(profile.body_color, "#eadfd6"),
        align=profile.blurb_align,
        leading=profile.body_size * 1.35,
        max_lines=max(1, round((profile.trim_height - 2.3) * 72 / (profile.body_size * 1.35))),
    )
    if profile.imprint:
        _draw_text_block(
            pdf,
            profile.imprint,
            x=back_x,
            y_top=(geometry.bleed + safe + 0.18) * inch,
            width=back_width,
            font=_font_name(profile.body_font, italic=True),
            size=max(7, profile.body_size - 1),
            color=_color(profile.body_color, "#eadfd6"),
            align="left",
            max_lines=2,
        )

    if profile.spine_text.strip() and geometry.spine_text_allowed:
        pdf.saveState()
        center_x = (geometry.spine_x + geometry.spine_width / 2) * inch
        center_y = (geometry.bleed + profile.trim_height / 2) * inch
        pdf.translate(center_x, center_y)
        pdf.rotate(90)
        pdf.setFillColorRGB(*_color(profile.title_color, "#f3e7da"))
        pdf.setFont(_font_name(profile.title_font, bold=True), profile.spine_size)
        available = max(0.1, profile.trim_height - geometry.spine_safe_inset * 2) * inch
        spine_text = profile.spine_text.strip()
        while stringWidth(spine_text, _font_name(profile.title_font, bold=True), profile.spine_size) > available and len(spine_text) > 4:
            spine_text = spine_text[:-2].rstrip() + "…"
        pdf.drawCentredString(0, -profile.spine_size / 3, spine_text)
        pdf.restoreState()

    _draw_barcode_area(pdf, slug, profile, geometry)
    pdf.showPage()
    pdf.save()


def _draw_pillow_text(image: Image.Image, profile: CoverProfile) -> None:
    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(image)
    width, height = image.size
    try:
        title_font = ImageFont.truetype("DejaVuSerif-Bold.ttf", max(20, round(profile.title_size * width / 720)))
        subtitle_font = ImageFont.truetype("DejaVuSerif-Italic.ttf", max(14, round(profile.subtitle_size * width / 720)))
        author_font = ImageFont.truetype("DejaVuSerif-Bold.ttf", max(14, round(profile.author_size * width / 720)))
    except OSError:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        author_font = ImageFont.load_default()

    def centered(text: str, y: float, font, fill: str, max_width: float) -> None:
        words = text.split()
        lines: list[str] = []
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            box = draw.textbbox((0, 0), candidate, font=font)
            if box[2] - box[0] <= max_width or not line:
                line = candidate
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        cursor = y
        for value in lines[:5]:
            box = draw.textbbox((0, 0), value, font=font)
            text_width = box[2] - box[0]
            draw.text(((width - text_width) / 2, cursor), value, font=font, fill=fill)
            cursor += (box[3] - box[1]) * 1.25

    centered(profile.title, height * 0.13, title_font, profile.title_color, width * 0.82)
    if profile.subtitle:
        centered(profile.subtitle, height * 0.36, subtitle_font, profile.subtitle_color, width * 0.78)
    if profile.author:
        centered(profile.author, height * 0.86, author_font, profile.author_color, width * 0.82)


def _render_ebook(slug: str, profile: CoverProfile, jpg_path: Path, png_path: Path) -> None:
    size = (profile.ebook_width_px, profile.ebook_height_px)
    image = Image.new("RGB", size, ImageColor.getrgb(profile.background_color))
    if profile.artwork_path:
        path = _asset_path(slug, profile.artwork_path)
        with Image.open(path) as source:
            art = source.convert("RGB")
            source_ratio = art.width / art.height
            target_ratio = size[0] / size[1]
            if source_ratio > target_ratio:
                crop_width = round(art.height * target_ratio)
                left = (art.width - crop_width) // 2
                art = art.crop((left, 0, left + crop_width, art.height))
            else:
                crop_height = round(art.width / target_ratio)
                top = (art.height - crop_height) // 2
                art = art.crop((0, top, art.width, top + crop_height))
            art = art.resize(size, Image.Resampling.LANCZOS)
            image.paste(art, (0, 0))
    _draw_pillow_text(image, profile)
    image.save(jpg_path, format="JPEG", quality=95, optimize=True, dpi=(72, 72))
    image.save(png_path, format="PNG", optimize=True)


def export_cover(slug: str, profile: CoverProfile) -> CoverExportResponse:
    validation = validate_cover(slug, profile)
    if not validation.valid:
        messages = "; ".join(issue.message for issue in validation.issues if issue.level == "error")
        raise ValueError(messages or "Cover configuration is not valid")
    save_cover_profile(slug, profile)
    export_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-cover-" + uuid4().hex[:8]
    directory = project_root(slug) / "exports" / export_id
    directory.mkdir(parents=True, exist_ok=True)
    base = re.sub(r"[^A-Za-z0-9]+", "-", profile.title.strip()).strip("-").casefold() or "cover"
    artifacts = []
    geometry = validation.geometry

    if profile.platform == "kdp_ebook":
        jpg_path = directory / f"{base}-ebook.jpg"
        png_path = directory / f"{base}-ebook-proof.png"
        _render_ebook(slug, profile, jpg_path, png_path)
        for fmt, path in (("jpg", jpg_path), ("png", png_path)):
            artifacts.append(
                {
                    "format": fmt,
                    "filename": path.name,
                    "relative_path": str(path.relative_to(project_root(slug))).replace("\\", "/"),
                    "bytes": path.stat().st_size,
                    "width": profile.ebook_width_px,
                    "height": profile.ebook_height_px,
                    "units": "px",
                }
            )
    else:
        pdf_path = directory / f"{base}-full-wrap.pdf"
        _render_print_pdf(slug, profile, geometry, pdf_path)
        artifacts.append(
            {
                "format": "pdf",
                "filename": pdf_path.name,
                "relative_path": str(pdf_path.relative_to(project_root(slug))).replace("\\", "/"),
                "bytes": pdf_path.stat().st_size,
                "width": geometry.cover_width,
                "height": geometry.cover_height,
                "units": "in",
            }
        )

    return CoverExportResponse(
        export_id=export_id,
        platform=profile.platform,
        geometry=geometry,
        validation=validation,
        artifacts=artifacts,
    )
