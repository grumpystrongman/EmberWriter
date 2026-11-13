"""Safe, atomic, local-only import of a multi-book EPUB ZIP into one Series Vault.

ZIP is never extracted to the filesystem. All books are parsed and checked
before database insertion. No canon assertions are created or auto-approved.
"""
from __future__ import annotations

import io
import re
import shutil
import zipfile
from pathlib import PurePosixPath

from ebooklib.exceptions import EpubException

from . import series_vault as vault
from .series_epub_safety import _check_nested_epub

MAX_ARCHIVE_BYTES = 60 * 1024 * 1024
MAX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_EPUBS = 150
MAX_ENTRIES = 300
_VOLUME_RE = re.compile(
    r"^(?P<prefix>.+?)\s+(?P<ordinal>\d{1,4})\s*[-–]\s*(?P<title>.+)\.epub$",
    re.IGNORECASE,
)


def _candidates(archive: zipfile.ZipFile) -> tuple[list[dict], int]:
    entries = archive.infolist()
    if len(entries) > MAX_ENTRIES:
        raise ValueError("Archive contains too many entries")
    result = []
    ignored = 0
    seen_names = set()
    seen_ordinals = set()
    total_size = 0
    for item in entries:
        name = item.filename.replace("\\", "/")
        if (name.startswith("/") or re.match(r"^[A-Za-z]:", name)
                or any(p == ".." for p in PurePosixPath(name).parts)):
            raise ValueError("ZIP member has unsafe path")
        if (item.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError("Archive contains a symbolic link")
        if item.is_dir():
            continue
        if not name.lower().endswith(".epub"):
            ignored += 1
            continue
        if item.flag_bits & 1:
            raise ValueError("Encrypted EPUBs are not supported")
        if len(result) >= MAX_EPUBS:
            raise ValueError("Archive exceeds the 150 EPUB import limit")
        if item.file_size > vault.MAX_IMPORT_BYTES or item.file_size <= 0:
            raise ValueError("An EPUB exceeds the 25 MB source limit")
        total_size += item.file_size
        if total_size > MAX_EXPANDED_BYTES:
            raise ValueError("Archive would exceed the 100 MB expanded-source limit")
        filename = PurePosixPath(name).name
        match = _VOLUME_RE.fullmatch(filename)
        if match is None:
            raise ValueError(
                f"Book order cannot be determined from '{filename}'. "
                "Use 'Series 001 - Book Title.epub' filenames."
            )
        ordinal = int(match["ordinal"])
        if not 1 <= ordinal <= 9999 or ordinal in seen_ordinals:
            raise ValueError(f"Duplicate or invalid book order: {ordinal}")
        if filename.casefold() in seen_names:
            raise ValueError(f"Duplicate filename: {filename}")
        seen_names.add(filename.casefold())
        seen_ordinals.add(ordinal)
        result.append({
            "entry": item,
            "filename": filename,
            "title": match["title"].strip(),
            "ordinal": ordinal,
        })
    if not result:
        raise ValueError("No numbered EPUB books were found in the ZIP")
    result.sort(key=lambda row: row["ordinal"])
    return result, ignored


def import_epub_zip(series_id: str, blob: bytes, *, rights_confirmed: bool,
                    edition_status: str = "reference") -> dict:
    if not rights_confirmed:
        raise ValueError("Confirm permission to add these books for local reference")
    if len(blob) > MAX_ARCHIVE_BYTES:
        raise ValueError("ZIP exceeds the 60 MB local import limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("Choose a valid EPUB ZIP archive") from exc
    with archive:
        candidates, ignored = _candidates(archive)
        existing = vault.series_detail(series_id)
        ordinals = {row["ordinal"] for row in existing["volumes"]}
        overlapping = sorted(ordinals.intersection(row["ordinal"] for row in candidates))
        if overlapping:
            raise ValueError(f"Books already exist at positions: {overlapping[:20]}")
        # Parse every book before mutating the vault. This is a deliberately
        # bounded, validated input; don't build a second ZIP extraction tree.
        prepared = []
        for row in candidates:
            raw = archive.read(row["entry"])
            _check_nested_epub(raw, row["filename"])
            try:
                text = vault._source_text(raw, row["filename"])
            except (EpubException, zipfile.BadZipFile) as exc:
                raise ValueError(f"EPUB could not be read: {row['filename']}") from exc
            prepared.append({**row, "text": text})
    # A failure during insertion rolls back the SQLite transaction and
    # cleans up snapshots created by this call, not other authors' files.
    created_volumes = []
    try:
        with vault._connect() as con:
            for row in prepared:
                volume_id = vault._insert_volume(
                    con, series_id, row["title"], row["ordinal"], "novel",
                    edition_status,
                )
                created_volumes.append(volume_id)
                source_id = vault._id()
                snapshot = vault._snapshot(volume_id, source_id, row["text"])
                import hashlib
                con.execute("INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?)", (
                    source_id, volume_id, row["filename"].removesuffix(".epub"),
                    row["filename"], 1, snapshot,
                    hashlib.sha256(row["text"].encode("utf-8")).hexdigest(),
                    len(row["text"].encode("utf-8")), vault.now(),
                ))
    except Exception:
        for volume_id in created_volumes:
            shutil.rmtree(vault._root() / "snapshots" / volume_id,
                          ignore_errors=True)
        raise
    return {
        "series_id": series_id,
        "imported_count": len(prepared),
        "book_orders": [r["ordinal"] for r in prepared],
        "total_source_characters": sum(len(r["text"]) for r in prepared),
        "ignored_non_epub": ignored,
        "source_snapshots_created": len(prepared),
        "canon_facts_approved": 0,
        "books": [{"ordinal": r["ordinal"], "title": r["title"]}
                  for r in prepared],
        "privacy": "All source snapshots remain on this computer.",
    }
