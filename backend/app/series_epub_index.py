"""Private, explicitly saved EPUB spine metadata, bound to immutable snapshots.

Does not retain original EPUB bytes. Revalidates the whole supplied EPUB on
save; frontend-submitted section positions are never trusted.
"""
from __future__ import annotations

import json

from . import series_epub_structure as epub_structure
from . import series_vault as vault


def _table(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS series_epub_structure_indexes(
            source_id TEXT PRIMARY KEY REFERENCES sources(id) ON DELETE CASCADE,
            series_id TEXT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
            source_hash TEXT NOT NULL,
            epub_hash TEXT NOT NULL,
            sections_json TEXT NOT NULL,
            saved_at TEXT NOT NULL
        )
    """)


def save(series_id: str, source_id: str, original_epub: bytes) -> dict:
    verified = epub_structure.preview(series_id, source_id, original_epub)
    if not verified["exact_snapshot_match"] or not verified["navigable"]:
        raise ValueError("EPUB does not exactly match the imported source, or has no usable spine")
    with vault._connect() as con:
        _table(con)
        con.execute("""
            INSERT INTO series_epub_structure_indexes
              (source_id,series_id,source_hash,epub_hash,sections_json,saved_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(source_id) DO UPDATE SET
              series_id=excluded.series_id,
              source_hash=excluded.source_hash,
              epub_hash=excluded.epub_hash,
              sections_json=excluded.sections_json,
              saved_at=excluded.saved_at
        """, (
            source_id, series_id, verified["source_hash"], verified["epub_hash"],
            json.dumps(verified["sections"], ensure_ascii=False), vault.now(),
        ))
    return {
        "saved": True, "source_id": source_id,
        "source_hash": verified["source_hash"],
        "matched_sections": len(verified["sections"]),
        "epub_hash": verified["epub_hash"],
        "author_confirmed": True,
        "story_sequence_inferred": False,
    }


def read(series_id: str, source_id: str) -> dict | None:
    source, text = vault.source_text(series_id, source_id)
    with vault._connect() as con:
        _table(con)
        row = con.execute("""
            SELECT source_hash,epub_hash,sections_json,saved_at
            FROM series_epub_structure_indexes
            WHERE series_id=? AND source_id=?
        """, (series_id, source_id)).fetchone()
    if row is None or row["source_hash"] != source["sha256"]:
        return None
    sections = json.loads(row["sections_json"])
    # Validate stored coordinates defensively; never expose unverified offsets.
    if not isinstance(sections, list) or len(sections) > epub_structure.MAX_SECTIONS:
        return None
    for section in sections:
        if (not isinstance(section, dict)
                or not isinstance(section.get("start"), int)
                or not isinstance(section.get("end"), int)
                or not 0 <= section["start"] < section["end"] <= len(text)):
            return None
    return {
        "sections": sections, "source_hash": row["source_hash"],
        "epub_hash": row["epub_hash"], "saved_at": row["saved_at"],
        "metadata_origin": "author_confirmed_original_epub",
        "source_length": len(text),
        "story_sequence_inferred": False,
    }


def overview(series_id: str) -> dict:
    """Fast structural coverage summary; no novel text in the response."""
    vault.series_detail(series_id)
    with vault._connect() as con:
        _table(con)
        total = con.execute("""
            SELECT COUNT(*)
            FROM sources s JOIN volumes v ON s.volume_id=v.id
            WHERE v.series_id=?
        """, (series_id,)).fetchone()[0]
        records = con.execute("""
            SELECT i.source_hash, i.sections_json, s.sha256
            FROM series_epub_structure_indexes i
            JOIN sources s ON s.id=i.source_id
            JOIN volumes v ON v.id=s.volume_id
            WHERE i.series_id=? AND v.series_id=?
        """, (series_id, series_id)).fetchall()
    indexed = 0
    section_count = 0
    toc_count = 0
    for row in records:
        if row["source_hash"] != row["sha256"]:
            continue
        try:
            sections = json.loads(row["sections_json"])
        except (ValueError, TypeError):
            continue
        if not isinstance(sections, list) or len(sections) > epub_structure.MAX_SECTIONS:
            continue
        if any(not isinstance(section, dict)
               or not isinstance(section.get("start"), int)
               or not isinstance(section.get("end"), int)
               or section["start"] < 0 or section["end"] <= section["start"]
               for section in sections):
            continue
        indexed += 1
        section_count += len(sections)
        toc_count += sum(s.get("confidence") == "exact_epub_toc_fragment" for s in sections)
    return {
        "series_id": series_id,
        "source_count": total,
        "indexed_sources": indexed,
        "unindexed_sources": max(0, total - indexed),
        "verified_sections": section_count,
        "toc_fragment_links": toc_count,
        "structural_only": True,
        "canon_assertions_created": 0,
        "story_sequence_inferred": False,
        "snapshot_fingerprints_checked": True,
        "source_text_returned": False,
    }
