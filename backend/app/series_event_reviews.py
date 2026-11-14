"""Author-reviewed, immutable-source-anchored narrative event ledger.

Staging never asserts a real event. Approval requires the author to supply an
interpretation and chronology class. No model can automatically approve.
"""
from __future__ import annotations

import sqlite3

from . import series_event_leads as event_leads
from . import series_vault as vault

VALID_KINDS = {"observed_event", "character_memory", "dream", "rumor", "hypothetical", "uncertain"}
VALID_TIME = {"book_sequence", "flashback", "flashforward", "time_unknown"}


def _ensure(con: sqlite3.Connection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS series_event_reviews (
          id TEXT PRIMARY KEY,
          series_id TEXT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
          source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
          source_hash TEXT NOT NULL,
          book INTEGER NOT NULL,
          quote_start INTEGER NOT NULL,
          quote_end INTEGER NOT NULL,
          quote TEXT NOT NULL,
          title TEXT NOT NULL DEFAULT '',
          event_kind TEXT NOT NULL DEFAULT 'uncertain',
          timeline_class TEXT NOT NULL DEFAULT 'time_unknown',
          note TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'proposed',
          created_at TEXT NOT NULL,
          reviewed_at TEXT,
          UNIQUE(series_id,source_id,quote_start,quote_end),
          CHECK(status IN ('proposed','approved','rejected'))
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS series_event_review_idx "
                "ON series_event_reviews(series_id,status,book,quote_start)")


def _record(con: sqlite3.Connection, sid: str, rid: str) -> dict:
    result = con.execute(
        "SELECT * FROM series_event_reviews WHERE id=? AND series_id=?",
        (rid, sid),
    ).fetchone()
    if result is None:
        raise FileNotFoundError("Event review not found in this series")
    return dict(result)


def _safe(series_id: str, row: dict) -> dict:
    source, content = vault.source_text(series_id, row["source_id"])
    valid = (source["sha256"] == row["source_hash"]
             and 0 <= row["quote_start"] < row["quote_end"] <= len(content)
             and content[row["quote_start"]:row["quote_end"]] == row["quote"])
    return {
        "id": row["id"], "series_id": row["series_id"],
        "source_id": row["source_id"], "book": row["book"],
        "quote_start": row["quote_start"], "quote_end": row["quote_end"],
        "quote": row["quote"] if valid else "",
        "title": row["title"], "event_kind": row["event_kind"],
        "timeline_class": row["timeline_class"], "status": row["status"],
        "note": row["note"], "source_verified": valid,
        "is_author_approved": row["status"] == "approved" and valid,
        "automatically_approved": False, "created_at": row["created_at"],
        "reviewed_at": row["reviewed_at"],
    }


def stage(series_id: str, source_id: str, quote_start: int, quote_end: int) -> dict:
    source, content = vault.source_text(series_id, source_id)
    if not 0 <= quote_start < quote_end <= len(content) or quote_end - quote_start > 400:
        raise ValueError("Invalid source event quote coordinates")
    # Fail closed against arbitrary author-independent statements: only the
    # independently reproducible literal event leads can enter this board.
    discovered = event_leads.scan(
        series_id, book=source["ordinal"], limit=250, offset=0
    )["leads"]
    match = next((row for row in discovered
                  if row["source_id"] == source_id and row["quote_start"] == quote_start
                  and row["quote_end"] == quote_end), None)
    if match is None:
        raise ValueError("Not a verified literal event lead in the selected source")
    with vault._connect() as con:
        _ensure(con)
        existing = con.execute(
            """SELECT * FROM series_event_reviews
               WHERE series_id=? AND source_id=? AND quote_start=? AND quote_end=?""",
            (series_id, source_id, quote_start, quote_end),
        ).fetchone()
        if existing:
            return _safe(series_id, dict(existing))
        identifier = vault._id()
        con.execute("""
            INSERT INTO series_event_reviews
            (id,series_id,source_id,source_hash,book,quote_start,quote_end,quote,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (identifier, series_id, source_id, source["sha256"],
              source["ordinal"], quote_start, quote_end,
              content[quote_start:quote_end], vault.now()))
        return _safe(series_id, _record(con, series_id, identifier))


def list_events(series_id: str, *, status: str = "all",
                book: int | None = None, limit: int = 200) -> dict:
    vault.series_detail(series_id)
    if status not in ("all", "proposed", "approved", "rejected"):
        raise ValueError("Invalid event review status")
    if not 1 <= limit <= 400:
        raise ValueError("Invalid event review limit")
    with vault._connect() as con:
        _ensure(con)
        rows = con.execute(
            "SELECT * FROM series_event_reviews WHERE series_id=? "
            "AND (?='all' OR status=?) AND (? IS NULL OR book=?) "
            "ORDER BY book,quote_start LIMIT ?",
            (series_id, status, status, book, book, limit),
        ).fetchall()
    events = [_safe(series_id, dict(row)) for row in rows]
    return {
        "series_id": series_id, "events": events,
        "total_visible": len(events), "status": status,
        "all_from_immutable_sources": all(item["source_verified"] for item in events),
        "author_approval_required": True,
        "story_time_inferred": False,
    }


def review(series_id: str, review_id: str, *, decision: str, title: str = "",
           event_kind: str = "uncertain", timeline_class: str = "time_unknown",
           note: str = "") -> dict:
    if decision not in ("approved", "rejected"):
        raise ValueError("Only approve or reject decisions are allowed")
    if event_kind not in VALID_KINDS or timeline_class not in VALID_TIME:
        raise ValueError("Choose a valid event interpretation and chronology class")
    if len(title) > 160 or len(note) > 1000:
        raise ValueError("Event review metadata exceeds limits")
    if decision == "approved" and (not title.strip() or event_kind == "uncertain"):
        raise ValueError("Approval requires an explicit title and author interpretation")
    with vault._connect() as con:
        _ensure(con)
        row = _record(con, series_id, review_id)
        checked = _safe(series_id, row)
        if not checked["source_verified"]:
            raise ValueError("Source snapshot mismatch; review must not proceed")
        con.execute("""
            UPDATE series_event_reviews SET status=?,title=?,event_kind=?,
                 timeline_class=?,note=?,reviewed_at=? WHERE id=? AND series_id=?
        """, (decision, title.strip(), event_kind, timeline_class,
              note.strip(), vault.now(), review_id, series_id))
        return _safe(series_id, _record(con, series_id, review_id))
