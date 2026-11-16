"""Preflight untrusted EPUB compressed containers before parsing any book XML.

A ZIP size alone does not bound its expanded contents. This common guard
is used by both single-book imports and bulk 80-book reference imports.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import PurePosixPath

MAX_EPUB_ENTRIES = 500
MAX_EPUB_EXPANDED_BYTES = 48 * 1024 * 1024
MAX_EPUB_SINGLE_ENTRY_BYTES = 16 * 1024 * 1024
MAX_EPUB_COMPRESSION_RATIO = 300


def _check_nested_epub(blob: bytes, filename: str) -> None:
    """Reject deceptive EPUB container structures before any XML/HTML parsing.

    ZIP compressed size is not sufficient to bound the amount of decompression.
    Inspect all declared inner members; this is a preflight, not a replacement
    for bounded extraction in a future isolated parser process.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as book:
            entries = book.infolist()
            if len(entries) > MAX_EPUB_ENTRIES:
                raise ValueError(f"EPUB has too many internal files: {filename}")
            total = 0
            # Check metadata before decompressing even the mimetype entry.
            mimetypes = [entry for entry in entries if entry.filename == "mimetype"]
            if not mimetypes:
                raise ValueError(f"EPUB is missing mimetype: {filename}")
            if len(mimetypes) != 1 or mimetypes[0].file_size != 20:
                raise ValueError(f"EPUB has invalid or duplicate mimetype: {filename}")
            for entry in entries:
                name = entry.filename.replace("\\", "/")
                if (name.startswith("/") or re.match(r"^[A-Za-z]:", name)
                        or ".." in PurePosixPath(name).parts):
                    raise ValueError(f"EPUB has unsafe inner path: {filename}")
                if entry.flag_bits & 1:
                    raise ValueError(f"EPUB has encrypted inner file: {filename}")
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError(f"EPUB has inner symlink: {filename}")
                if entry.is_dir():
                    continue
                if entry.file_size > MAX_EPUB_SINGLE_ENTRY_BYTES:
                    raise ValueError(f"EPUB contains oversized internal content: {filename}")
                total += entry.file_size
                if total > MAX_EPUB_EXPANDED_BYTES:
                    raise ValueError(f"EPUB expanded content exceeds limit: {filename}")
                if entry.file_size > 1_048_576 and (
                        entry.compress_size == 0 or
                        entry.file_size / max(1, entry.compress_size)
                        > MAX_EPUB_COMPRESSION_RATIO):
                    raise ValueError(f"EPUB has unsafe compression ratio: {filename}")
            if book.read(mimetypes[0]) != b"application/epub+zip":
                raise ValueError(f"EPUB has invalid mimetype: {filename}")
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError) as exc:
        raise ValueError(f"EPUB container is invalid: {filename}") from exc
