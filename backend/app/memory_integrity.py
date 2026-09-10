from __future__ import annotations

import hashlib
import sqlite3
from typing import Any

from .storage import _connect, read_text


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _memory_tables_exist(con: sqlite3.Connection) -> bool:
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name IN ('document_analysis', 'narrative_facts')"
    ).fetchall()
    return {row["name"] for row in rows} == {"document_analysis", "narrative_facts"}


def reconcile_story_memory(slug: str) -> dict[str, Any]:
    """Remove derived memory whose source manuscript no longer matches its analyzed hash.

    Manuscript files remain authoritative. This reconciliation is intentionally destructive only
    to rebuildable derived Story Memory; author-owned manuscript/story-bible files are untouched.
    """

    stale_paths: list[str] = []
    orphan_fact_count = 0

    with _connect(slug) as con:
        if not _memory_tables_exist(con):
            return {"stale_paths": [], "facts_removed": 0, "analyses_removed": 0}

        analyses = con.execute(
            "SELECT path, content_hash FROM document_analysis ORDER BY path"
        ).fetchall()
        for row in analyses:
            path = str(row["path"])
            try:
                current = read_text(slug, path)
            except (FileNotFoundError, OSError, UnicodeError, ValueError):
                stale_paths.append(path)
                continue
            if _hash(current) != row["content_hash"]:
                stale_paths.append(path)

        facts_removed = 0
        analyses_removed = 0
        if stale_paths:
            placeholders = ",".join("?" for _ in stale_paths)
            result = con.execute(
                f"DELETE FROM narrative_facts WHERE source_path IN ({placeholders})",
                stale_paths,
            )
            facts_removed += max(0, result.rowcount)
            result = con.execute(
                f"DELETE FROM document_analysis WHERE path IN ({placeholders})",
                stale_paths,
            )
            analyses_removed += max(0, result.rowcount)

        orphan_result = con.execute(
            "DELETE FROM narrative_facts "
            "WHERE source_path NOT IN (SELECT path FROM document_analysis)"
        )
        orphan_fact_count = max(0, orphan_result.rowcount)
        facts_removed += orphan_fact_count

    if stale_paths or orphan_fact_count:
        # Import lazily to avoid a module cycle: memory imports storage, not this module.
        from .memory import export_memory

        export_memory(slug)

    return {
        "stale_paths": stale_paths,
        "facts_removed": facts_removed,
        "analyses_removed": analyses_removed,
    }
