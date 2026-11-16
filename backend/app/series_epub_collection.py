"""Author-controlled local EPUB ZIP structure recovery, never a manuscript reimport.

Every member is checked against the immutable Series Vault source. Preview is
read-only. Confirmation revalidates the entire bounded archive before a single
atomic SQLite transaction. Neither path retains original EPUB bytes.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import PurePosixPath

from . import series_bulk_import as bulk
from . import series_epub_index as index
from . import series_epub_structure as structure
from . import series_vault as vault


def _inspect(series_id: str, blob: bytes) -> tuple[list[dict], list[dict]]:
    if len(blob) > bulk.MAX_ARCHIVE_BYTES:
        raise ValueError("Archive exceeds the 60 MB EPUB ZIP limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError("Select a valid EPUB collection ZIP") from exc
    with archive:
        members, _ignored = bulk._candidates(archive)
        details = vault.series_detail(series_id)
        by_order = {row["ordinal"]: row for row in details["volumes"]}
        rows: list[dict] = []
        verified: list[dict] = []
        for member in members:
            volume = by_order.get(member["ordinal"])
            source = next((
                item for item in (volume or {}).get("sources", [])
                if PurePosixPath(item["source_path"].replace("\\", "/")).name.casefold()
                == member["filename"].casefold()
            ), None)
            if not source:
                rows.append({
                    "ordinal": member["ordinal"], "filename": member["filename"],
                    "status": "source_not_found", "matched_sections": 0,
                    "reason": "No imported source matches this book number and filename",
                })
                continue
            try:
                original = archive.read(member["entry"])
                checked = structure.preview(series_id, source["id"], original)
            except (ValueError, zipfile.BadZipFile, OSError):
                rows.append({
                    "ordinal": member["ordinal"], "filename": member["filename"],
                    "status": "unreadable_epub", "matched_sections": 0,
                    "reason": "Original EPUB cannot be safely reconciled",
                })
                continue
            if not checked["exact_snapshot_match"] or not checked["navigable"]:
                rows.append({
                    "ordinal": member["ordinal"], "filename": member["filename"],
                    "status": checked["status"], "matched_sections": 0,
                    "reason": checked["message"],
                })
                continue
            rows.append({
                "ordinal": member["ordinal"], "filename": member["filename"],
                "status": "exact_match", "matched_sections": checked["matched_sections"],
                "reason": "Original EPUB matches immutable source snapshot",
            })
            verified.append(checked)
    return rows, verified


def preview(series_id: str, blob: bytes) -> dict:
    rows, verified = _inspect(series_id, blob)
    matches = len(verified)
    can_confirm = matches > 0 and matches == len(rows)
    return {
        "series_id": series_id, "books_in_archive": len(rows),
        "matched_books": matches, "unmatched_books": len(rows) - matches,
        "recoverable_sections": sum(item["matched_sections"] for item in rows),
        "books": rows, "can_confirm": can_confirm,
        "saved": False, "source_text_changed": False,
        "canon_approved": False, "story_sequence_inferred": False,
        "message": (
            "All EPUB members match saved sources; explicit confirmation can save indexes."
            if can_confirm else
            "One or more members could not be reconciled. No indexes can be saved until the archive matches."
        ),
    }


def confirm(series_id: str, blob: bytes) -> dict:
    # Strict all-or-nothing: parsing and provenance checks before a write.
    rows, verified = _inspect(series_id, blob)
    if not rows or len(rows) != len(verified):
        raise ValueError("Archive contains unmatched EPUBs; indexes not saved")
    with vault._connect() as con:
        index._table(con)
        con.executemany("""
            INSERT INTO series_epub_structure_indexes
              (source_id,series_id,source_hash,epub_hash,sections_json,saved_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(source_id) DO UPDATE SET
              series_id=excluded.series_id,
              source_hash=excluded.source_hash,
              epub_hash=excluded.epub_hash,
              sections_json=excluded.sections_json,
              saved_at=excluded.saved_at
        """, [
            (item["source_id"], series_id, item["source_hash"], item["epub_hash"],
             json.dumps(item["sections"], ensure_ascii=False), vault.now())
            for item in verified
        ])
    return {
        "series_id": series_id, "saved": True,
        "indexed_books": len(verified),
        "indexed_sections": sum(len(item["sections"]) for item in verified),
        "source_text_changed": False, "canon_approved": False,
        "story_sequence_inferred": False,
        "message": "Verified chapter indexes saved locally. Original EPUBs were not retained.",
    }
