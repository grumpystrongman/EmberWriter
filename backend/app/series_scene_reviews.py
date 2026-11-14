"""Source-bound author review ledger for proposed literary scenes.

This does not write Canon Graph assertions. Only the author can approve a scene
classification and viewpoint, and all stored coordinates/hashes are checked
against the immutable vault source before they are shown as verified.
"""
from __future__ import annotations

import hashlib

from . import series_canon as canon
from . import series_scene_windows as windows
from . import series_vault as vault

KINDS = {"actual_scene", "narrative_transition", "recollection", "dream",
         "front_matter", "non_scene", "uncertain"}
POV = {"undetermined", "first_person", "third_limited",
       "third_omniscient", "second_person", "mixed_other"}
STATUSES = {"proposed", "approved", "rejected"}


def _ensure(con) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS series_scene_reviews (
          id TEXT PRIMARY KEY,
          series_id TEXT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
          source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
          source_hash TEXT NOT NULL,
          range_hash TEXT NOT NULL,
          book INTEGER NOT NULL,
          start INTEGER NOT NULL,
          end INTEGER NOT NULL,
          title TEXT NOT NULL DEFAULT '',
          scene_kind TEXT NOT NULL DEFAULT 'uncertain',
          pov_style TEXT NOT NULL DEFAULT 'undetermined',
          pov_character_id TEXT REFERENCES entities(id) ON DELETE SET NULL,
          note TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'proposed',
          created_at TEXT NOT NULL,
          reviewed_at TEXT,
          UNIQUE(series_id,source_id,start,end),
          CHECK(status IN ('proposed','approved','rejected'))
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS scene_reviews_book_idx "
                "ON series_scene_reviews(series_id,book,start)")


def _get(con, series_id: str, review_id: str) -> dict:
    row = con.execute(
        "SELECT * FROM series_scene_reviews WHERE series_id=? AND id=?",
        (series_id, review_id),
    ).fetchone()
    if row is None:
        raise FileNotFoundError("Scene review not found in this series")
    return dict(row)


def _public(series_id: str, record: dict) -> dict:
    source, content = vault.source_text(series_id, record["source_id"])
    start, end = record["start"], record["end"]
    valid = (source["sha256"] == record["source_hash"] and
             source["ordinal"] == record["book"] and
             isinstance(start, int) and isinstance(end, int) and
             0 <= start < end <= len(content) and
             hashlib.sha256(content[start:end].encode("utf8")).hexdigest()
             == record["range_hash"])
    return {
        "id":record["id"], "source_id":record["source_id"],
        "book":record["book"], "start":start, "end":end,
        "source_hash":record["source_hash"], "range_hash":record["range_hash"],
        "title":record["title"], "scene_kind":record["scene_kind"],
        "pov_style":record["pov_style"], "pov_character_id":record["pov_character_id"],
        "note":record["note"], "status":record["status"],
        "source_verified":valid,
        "author_confirmed_scene": bool(valid and record["status"]=="approved"
                                       and record["scene_kind"]=="actual_scene"),
        "auto_scene_approved":False,
        "created_at":record["created_at"], "reviewed_at":record["reviewed_at"],
        "excerpt":content[start:min(end,start+240)] if valid else "",
    }


def stage(series_id: str, *, source_id: str, book: int,
          start: int, end: int) -> dict:
    candidate = windows.detail(series_id, book=book, source_id=source_id,
                               start=start, end=end)
    source, _ = vault.source_text(series_id, source_id)
    with vault._connect() as con:
        _ensure(con)
        found = con.execute("""
            SELECT id FROM series_scene_reviews
            WHERE series_id=? AND source_id=? AND start=? AND end=?
        """, (series_id, source_id, start, end)).fetchone()
        if found:
            return _public(series_id, _get(con, series_id, found["id"]))
        rid = vault._id()
        con.execute("""
            INSERT INTO series_scene_reviews
            (id,series_id,source_id,source_hash,range_hash,book,start,end,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (rid, series_id, source_id, source["sha256"],
              candidate["range_hash"], book, start, end, vault.now()))
        return _public(series_id, _get(con, series_id, rid))


def list_reviews(series_id: str, *, book: int | None = None) -> list[dict]:
    vault.series_detail(series_id)
    with vault._connect() as con:
        _ensure(con)
        rows = con.execute("""
            SELECT * FROM series_scene_reviews
            WHERE series_id=? AND (? IS NULL OR book=?)
            ORDER BY book,start LIMIT 250
        """, (series_id, book, book)).fetchall()
    return [_public(series_id, dict(row)) for row in rows]


def decide(series_id: str, review_id: str, *, decision: str,
           title: str = "", kind: str = "uncertain",
           pov_style: str = "undetermined",
           pov_character_id: str | None = None, note: str = "") -> dict:
    if decision not in ("approved", "rejected") or kind not in KINDS or pov_style not in POV:
        raise ValueError("Invalid scene review classification")
    if len(title)>160 or len(note)>1000:
        raise ValueError("Scene review text too long")
    if decision=="approved" and (kind=="uncertain" or not title.strip()):
        raise ValueError("Choose a scene classification and meaningful title to approve")
    with vault._connect() as con:
        _ensure(con)
        before = _get(con, series_id, review_id)
        if not _public(series_id, before)["source_verified"]:
            raise ValueError("Original source does not match the review")
        if pov_character_id:
            found = next((entity for entity in canon.list_entities(series_id)
                          if entity["id"]==pov_character_id and entity["kind"]=="character"),None)
            if not found:
                raise ValueError("POV character must belong to this series")
        con.execute("""
            UPDATE series_scene_reviews
            SET status=?,title=?,scene_kind=?,pov_style=?,pov_character_id=?,note=?,reviewed_at=?
            WHERE series_id=? AND id=?
        """, (decision,title.strip(),kind,pov_style,pov_character_id,note.strip(),
              vault.now(),series_id,review_id))
        return _public(series_id, _get(con, series_id, review_id))
