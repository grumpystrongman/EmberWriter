"""Read-only EPUB spine reconciliation against an immutable Series Vault snapshot.

Never guesses positions or story chronology. A section is navigable only if the
original EPUB document's extracted text matches the saved snapshot at a unique
exact offset. The source snapshot and original EPUB remain unchanged.
"""
from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import PurePosixPath

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub
from ebooklib.exceptions import EpubException

from . import series_vault as vault
from .series_epub_safety import _check_nested_epub

MAX_SECTIONS = 400


def preview(series_id: str, source_id: str, blob: bytes) -> dict:
    source, saved = vault.source_text(series_id, source_id)
    if not source["source_path"].lower().endswith(".epub"):
        raise ValueError("Original EPUB structure can only be matched to an EPUB source")
    if len(blob) > vault.MAX_IMPORT_BYTES:
        raise ValueError("Original EPUB exceeds the local import size limit")
    _check_nested_epub(blob, "original.epub")
    try:
        book = epub.read_epub(io.BytesIO(blob))
    except (EpubException, zipfile.BadZipFile, KeyError, OSError) as exc:
        raise ValueError("Original EPUB has invalid publication metadata") from exc
    # Use the same extraction convention as the original importer; order can
    # differ from the spine, so matching is by exact saved text, not guessed offset.
    documents = [item for item in book.get_items() if item.get_type() == ITEM_DOCUMENT]
    extracted = []
    for item in documents:
        content = BeautifulSoup(item.get_content(), "html.parser").get_text(" ", strip=True)
        content = content.translate({0x00AD: None, 0x200B: None, 0xFEFF: None})
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        extracted.append((item, content))
    original = "\n\n".join(content for _, content in extracted)
    same_snapshot = original == saved
    if not same_snapshot:
        return {
            "series_id": series_id, "source_id": source_id,
            "source_hash": source["sha256"], "epub_hash": hashlib.sha256(blob).hexdigest(),
            "exact_snapshot_match": False, "navigable": False, "sections": [],
            "spine_items": len(book.spine), "matched_sections": 0,
            "status": "edition_mismatch",
            "message": "Original EPUB text or extraction order differs from the immutable source. No offsets are accepted; review the edition before reindexing.",
            "story_sequence_inferred": False, "saved": False,
        }
    # The saved snapshot is exactly the concatenation of importer item text.
    # Index boundaries in that immutable string without approximate searching.
    offsets: dict[str, tuple[int, int]] = {}
    cursor = 0
    for index, (item, content) in enumerate(extracted):
        if index:
            cursor += 2
        start = cursor
        cursor += len(content)
        offsets[item.id] = (start, cursor)
    if cursor != len(saved):
        raise ValueError("EPUB text offsets did not reconcile exactly")
    by_id = {item.id: item for item, _ in extracted}
    rows = []
    for item_ref in book.spine:
        item_id = item_ref[0] if isinstance(item_ref, (list, tuple)) else item_ref
        item = by_id.get(item_id)
        if item is None or item_id not in offsets:
            continue
        start, end = offsets[item_id]
        if start == end:
            continue
        # Prefer an explicit XHTML heading when present. If absent, show only
        # the file name; never manufacture a numbered chapter or story event.
        html = BeautifulSoup(item.get_content(), "html.parser")
        heading = html.find(["h1", "h2", "h3"])
        explicit_title = heading.get_text(" ", strip=True)[:120] if heading else ""
        name = PurePosixPath(item.file_name).name
        title = explicit_title or name[:120]
        rows.append({
            "index": len(rows) + 1, "title": title,
            "start": start, "end": end, "characters": end - start,
            "source_item": item.file_name, "heading_detected": bool(explicit_title),
            "confidence": "exact_spine_with_explicit_heading" if explicit_title else "exact_epub_spine_document",
            "author_confirmed": False,
        })
        if len(rows) >= MAX_SECTIONS:
            break
    return {
        "series_id": series_id, "source_id": source_id,
        "source_hash": source["sha256"], "epub_hash": hashlib.sha256(blob).hexdigest(),
        "exact_snapshot_match": True, "navigable": bool(rows),
        "sections": rows, "spine_items": len(book.spine),
        "matched_sections": len(rows),
        "status": "exact_match" if rows else "no_spine_documents",
        "message": "Exact source offsets recovered from the original EPUB spine. Explicit XHTML headings are labeled; otherwise only filenames are shown. No story chronology was inferred.",
        "story_sequence_inferred": False, "saved": False,
    }
