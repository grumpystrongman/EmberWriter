"""Immutable quote-anchored author decisions for uncertain dialogue speakers and POV."""
from __future__ import annotations

import sqlite3

from . import series_canon as canon
from . import series_dialogue_leads as dialogue
from . import series_vault as vault

POV = {"not_determined", "first_person", "third_limited", "third_omniscient", "other"}
STATUS = {"proposed", "approved", "rejected"}


def _ensure(con: sqlite3.Connection):
    con.execute("""
        CREATE TABLE IF NOT EXISTS series_dialogue_reviews (
          id TEXT PRIMARY KEY,
          series_id TEXT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
          source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
          source_hash TEXT NOT NULL,
          book INTEGER NOT NULL,
          quote_start INTEGER NOT NULL,
          quote_end INTEGER NOT NULL,
          quote TEXT NOT NULL,
          speaker_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
          pov_class TEXT NOT NULL DEFAULT 'not_determined',
          note TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'proposed',
          created_at TEXT NOT NULL,
          reviewed_at TEXT,
          UNIQUE(series_id,source_id,quote_start,quote_end),
          CHECK(status IN ('proposed','approved','rejected'))
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS dialogue_review_idx "
                "ON series_dialogue_reviews(series_id,book,quote_start)")


def _get(con: sqlite3.Connection, series_id: str, review_id: str) -> dict:
    row = con.execute("SELECT * FROM series_dialogue_reviews WHERE series_id=? AND id=?",
                      (series_id, review_id)).fetchone()
    if row is None:
        raise FileNotFoundError("Dialogue review not found in series")
    return dict(row)


def _safe(series_id: str, row: dict) -> dict:
    record, content = vault.source_text(series_id, row["source_id"])
    verified = (record["sha256"] == row["source_hash"]
                and 0 <= row["quote_start"] < row["quote_end"] <= len(content)
                and content[row["quote_start"]:row["quote_end"]] == row["quote"])
    return {
        "id": row["id"], "series_id": row["series_id"], "source_id": row["source_id"],
        "source_hash": row["source_hash"], "book": row["book"],
        "quote_start": row["quote_start"], "quote_end": row["quote_end"],
        "quote": row["quote"] if verified else "",
        "speaker_id": row["speaker_id"], "pov_class": row["pov_class"],
        "note": row["note"], "status": row["status"],
        "source_verified": verified,
        "author_confirmed_speaker": bool(verified and row["status"] == "approved"
                                        and row["speaker_id"]),
        "model_speaker_approved": False, "created_at": row["created_at"],
        "reviewed_at": row["reviewed_at"],
    }


def stage(series_id: str, source_id: str, start: int, end: int) -> dict:
    source, content = vault.source_text(series_id, source_id)
    if not 0 <= start < end <= len(content) or end-start > 350:
        raise ValueError("Invalid quote coordinates")
    # Reproduce the candidate in this one exact book before author staging.
    matches = dialogue.scan(series_id, book=source["ordinal"], limit=100, offset=0)
    # The bounded scan may have up to 500 proposals: verify every accessible page.
    while True:
        if any(x["source_id"] == source_id and x["quote_start"] == start
               and x["quote_end"] == end for x in matches["leads"]):
            break
        next_offset = matches.get("_offset", 0) + len(matches["leads"])
        if not matches["leads"] or next_offset >= matches["total"]:
            raise ValueError("Quote is not a verified dialogue attribution lead")
        matches = dialogue.scan(series_id, book=source["ordinal"],
                                limit=100, offset=next_offset)
        matches["_offset"] = next_offset
    with vault._connect() as con:
        _ensure(con)
        existing = con.execute("""
            SELECT id FROM series_dialogue_reviews
            WHERE series_id=? AND source_id=? AND quote_start=? AND quote_end=?
        """, (series_id, source_id, start, end)).fetchone()
        if existing:
            return _safe(series_id, _get(con, series_id, existing["id"]))
        rid = vault._id()
        con.execute("""
            INSERT INTO series_dialogue_reviews
            (id,series_id,source_id,source_hash,book,quote_start,quote_end,quote,created_at)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (rid, series_id, source_id, source["sha256"], source["ordinal"],
              start, end, content[start:end], vault.now()))
        return _safe(series_id, _get(con, series_id, rid))


def list_reviews(series_id: str, book: int | None = None) -> list[dict]:
    vault.series_detail(series_id)
    with vault._connect() as con:
        _ensure(con)
        rows = con.execute("""
            SELECT * FROM series_dialogue_reviews
            WHERE series_id=? AND (? IS NULL OR book=?)
            ORDER BY book,quote_start LIMIT 250
        """, (series_id, book, book)).fetchall()
    return [_safe(series_id, dict(row)) for row in rows]


def decide(series_id: str, review_id: str, *, decision: str,
           speaker_id: str | None = None, pov_class: str = "not_determined",
           note: str = "") -> dict:
    if decision not in ("approved", "rejected") or pov_class not in POV or len(note) > 1000:
        raise ValueError("Invalid author decision or viewpoint class")
    if decision == "approved" and not speaker_id:
        raise ValueError("Choose an actual speaker before approving dialogue")
    with vault._connect() as con:
        _ensure(con)
        previous = _get(con, series_id, review_id)
        if not _safe(series_id, previous)["source_verified"]:
            raise ValueError("Source changed; cannot approve an unverified quote")
        if speaker_id:
            character = next((item for item in canon.list_entities(series_id)
                              if item["id"] == speaker_id and item["kind"] == "character"), None)
            if character is None:
                raise ValueError("Speaker must be a character in this series")
        con.execute("""
            UPDATE series_dialogue_reviews
            SET status=?,speaker_id=?,pov_class=?,note=?,reviewed_at=?
            WHERE id=? AND series_id=?
        """, (decision, speaker_id, pov_class, note.strip(),
              vault.now(), review_id, series_id))
        return _safe(series_id, _get(con, series_id, review_id))
