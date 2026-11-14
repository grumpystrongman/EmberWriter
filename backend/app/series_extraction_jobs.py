"""Resumable, explicitly authorized private extraction of one source at a time.

Jobs advance only when the author invokes the next batch. No automatic
background scanning, canon promotion, remote-provider fallback or manuscript
writes. Each candidate is verified by series_suggestions against exact immutable
source text; all persisted state remains in the local Series Vault database.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from . import series_suggestions as suggestions
from . import series_vault as vault

WINDOW_CHARS = 1400
MAX_STORED_SUGGESTIONS = 600
LEASE_SECONDS = 150


def _plan_window(series_id: str, source_id: str, content: str, start: int) -> tuple[int, str]:
    """Honor author-confirmed EPUB spine boundaries without skipping source bytes.

    Unconfirmed structure is never used. Otherwise retain the existing safe
    1,400-character sentence/paragraph bounded behavior.
    """
    limit = min(start + WINDOW_CHARS, len(content))
    from . import series_epub_index
    saved = series_epub_index.read(series_id, source_id)
    if saved is not None:
        boundaries = sorted({
            section["start"] for section in saved["sections"]
            if start < section["start"] <= limit
        })
        if boundaries:
            return boundaries[0], "author_confirmed_epub_spine"
    if limit < len(content):
        last = max(content.rfind(".", start + 500, limit),
                   content.rfind("!", start + 500, limit),
                   content.rfind("?", start + 500, limit),
                   content.rfind("\n", start + 500, limit))
        if last > start + 500:
            return last + 1, "sentence_or_paragraph"
    return limit, "bounded_source_window"


def _ensure(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS series_extraction_jobs(
            id TEXT PRIMARY KEY, series_id TEXT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
            source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            source_hash TEXT NOT NULL, model TEXT NOT NULL,
            next_offset INTEGER NOT NULL DEFAULT 0,
            source_length INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'ready',
            processed_windows INTEGER NOT NULL DEFAULT 0,
            candidate_json TEXT NOT NULL DEFAULT '[]',
            discarded INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NOT NULL DEFAULT '',
            leased_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            CHECK (status IN ('ready','running','error','complete','cancelled'))
        )
    """)
    con.execute("""CREATE INDEX IF NOT EXISTS series_extraction_jobs_idx
                   ON series_extraction_jobs(series_id,source_id,created_at)""")


def _row(con: sqlite3.Connection, series_id: str, job_id: str) -> dict:
    value = con.execute(
        "SELECT * FROM series_extraction_jobs WHERE id=? AND series_id=?",
        (job_id, series_id),
    ).fetchone()
    if not value:
        raise FileNotFoundError("Source extraction job not found")
    return dict(value)


def _public(row: dict, *, include_candidates: bool = True) -> dict:
    candidates = json.loads(row["candidate_json"])
    result = {
        "id": row["id"], "series_id": row["series_id"],
        "source_id": row["source_id"], "status": row["status"],
        "source_hash": row["source_hash"], "source_length": row["source_length"],
        "next_offset": row["next_offset"],
        "progress_percent": round(100 * row["next_offset"] / max(1, row["source_length"]), 1),
        "processed_windows": row["processed_windows"],
        "candidate_count": len(candidates), "discarded": row["discarded"],
        "model": row["model"], "error": row["last_error"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        "all_candidates_unsaved": True, "auto_canon_approved": False,
        "execution_mode": "author_initiated_single_window",
    }
    if include_candidates:
        result["candidates"] = candidates
    return result


def _source(series_id: str, source_id: str) -> tuple[dict, str]:
    return vault.source_text(series_id, source_id)


def create(series_id: str, source_id: str, model: str) -> dict:
    model = model.strip()
    if not 1 <= len(model) <= 200 or any(c in model for c in "\r\n\x00"):
        raise ValueError("Choose one installed local model")
    source, text = _source(series_id, source_id)
    if not text.strip():
        raise ValueError("This source contains no usable text")
    if not vault.series_detail(series_id)["volumes"]:
        raise ValueError("Series Vault must contain an imported source")
    stamp = vault.now()
    with vault._connect() as con:
        _ensure(con)
        existing = con.execute("""
            SELECT * FROM series_extraction_jobs
            WHERE series_id=? AND source_id=? AND source_hash=? AND model=?
              AND status IN ('ready','running','error','complete')
            ORDER BY created_at DESC LIMIT 1
        """, (series_id, source_id, source["sha256"], model)).fetchone()
        if existing:
            return _public(dict(existing))
        identifier = vault._id()
        con.execute("""INSERT INTO series_extraction_jobs
            (id,series_id,source_id,source_hash,model,next_offset,source_length,
             status,processed_windows,candidate_json,discarded,last_error,leased_at,
             created_at,updated_at)
            VALUES (?,?,?,?,?,0,?,'ready',0,'[]',0,'',NULL,?,?)""",
                    (identifier, series_id, source_id, source["sha256"], model,
                     len(text), stamp, stamp))
        return _public(_row(con, series_id, identifier))


def get(series_id: str, job_id: str) -> dict:
    vault.series_detail(series_id)
    with vault._connect() as con:
        _ensure(con)
        return _public(_row(con, series_id, job_id))


def list_jobs(series_id: str, source_id: str | None = None) -> list[dict]:
    vault.series_detail(series_id)
    with vault._connect() as con:
        _ensure(con)
        where = "series_id=?"
        args = [series_id]
        if source_id:
            _source(series_id, source_id)
            where += " AND source_id=?"
            args.append(source_id)
        rows = con.execute(
            "SELECT * FROM series_extraction_jobs WHERE " + where +
            " ORDER BY created_at DESC LIMIT 30", tuple(args)).fetchall()
        return [_public(dict(row), include_candidates=False) for row in rows]


def cancel(series_id: str, job_id: str) -> dict:
    with vault._connect() as con:
        _ensure(con)
        row = _row(con, series_id, job_id)
        if row["status"] == "running":
            raise ValueError("An extraction window is running. Retry cancellation after it finishes")
        if row["status"] != "cancelled":
            con.execute(
                "UPDATE series_extraction_jobs SET status='cancelled', updated_at=? WHERE id=?",
                (vault.now(), job_id),
            )
        return _public(_row(con, series_id, job_id))


async def advance(series_id: str, job_id: str) -> dict:
    # Reservation is atomic at the SQLite row level. No duplicate processing
    # from parallel API requests; stale leases are recoverable after a crash.
    with vault._connect() as con:
        _ensure(con)
        row = _row(con, series_id, job_id)
        if row["status"] == "cancelled":
            raise ValueError("Cancelled extraction cannot be resumed")
        if row["status"] == "complete":
            return _public(row)
        if row["status"] == "running":
            try:
                leased = datetime.fromisoformat(row["leased_at"])
            except (TypeError, ValueError):
                leased = datetime.min.replace(tzinfo=UTC)
            if datetime.now(UTC) - leased < timedelta(seconds=LEASE_SECONDS):
                raise ValueError("This source window is already running")
            con.execute("""UPDATE series_extraction_jobs SET status='error',
                last_error='Interrupted extraction lease expired; safe to retry'
                WHERE id=? AND status='running'""", (job_id,))
        updated = con.execute("""UPDATE series_extraction_jobs SET status='running',
                leased_at=?,last_error='',updated_at=?
                WHERE id=? AND status IN ('ready','error')""",
            (vault.now(), vault.now(), job_id))
        if updated.rowcount != 1:
            raise ValueError("Extraction job was changed by another request")
        row = _row(con, series_id, job_id)

    source, content = _source(series_id, row["source_id"])
    if source["sha256"] != row["source_hash"] or len(content) != row["source_length"]:
        with vault._connect() as con:
            _ensure(con)
            con.execute("""UPDATE series_extraction_jobs SET status='error',
                last_error=?, leased_at=NULL, updated_at=? WHERE id=?""",
                ("Source snapshot changed; manual review required", vault.now(), job_id))
        raise ValueError("The original source snapshot no longer matches this job")

    start = row["next_offset"]
    # One strictly bounded window; author-confirmed EPUB structure takes
    # precedence over heuristic punctuation. No offsets are skipped.
    stop, boundary_kind = _plan_window(series_id, row["source_id"], content, start)
    try:
        result = await suggestions.suggest_facts(
            series_id, row["source_id"], start, stop, row["model"],
        )
    except Exception as exc:
        # Do not log source text or raw model output.
        message = ("Local model timed out; retry this window"
                   if isinstance(exc, TimeoutError)
                   else "Local extraction failed; check model and retry")
        with vault._connect() as con:
            _ensure(con)
            con.execute("""UPDATE series_extraction_jobs
                SET status='error', last_error=?,leased_at=NULL,updated_at=?
                WHERE id=? AND status='running'""",
                (message, vault.now(), job_id))
        raise

    with vault._connect() as con:
        _ensure(con)
        fresh = _row(con, series_id, job_id)
        if fresh["status"] != "running" or fresh["next_offset"] != start:
            raise ValueError("Extraction was concurrently changed; no candidates saved")
        candidates = json.loads(fresh["candidate_json"])
        keys = {(c["source_id"], c["quote_start"], c["predicate"], c["subject_id"])
                for c in candidates}
        new = []
        # Defense in depth: validate exact source coordinates even if the
        # extraction adapter changes or returns malformed model output.
        from . import series_canon as canon
        valid_entities = {item["id"]: item for item in canon.list_entities(series_id)}
        discarded_invalid = 0
        for item in result["suggestions"]:
            if not isinstance(item, dict):
                discarded_invalid += 1
                continue
            quote = item.get("quote")
            qstart = item.get("quote_start")
            qend = item.get("quote_end")
            who = item.get("subject_id")
            knower = item.get("knower_id")
            scope = item.get("scope")
            if (item.get("source_id") != row["source_id"]
                    or not isinstance(qstart, int) or not isinstance(qend, int)
                    or not start <= qstart < qend <= stop
                    or not isinstance(quote, str)
                    or len(quote) > 1000 or content[qstart:qend] != quote
                    or not isinstance(who, str) or who not in valid_entities
                    or not isinstance(item.get("predicate"), str)
                    or not 1 <= len(item["predicate"]) <= 60
                    or not isinstance(item.get("object_text"), str)
                    or not 1 <= len(item["object_text"]) <= 500
                    or not isinstance(scope, str) or scope not in canon.SCOPES
                    or (scope == "character_belief" and
                        (not isinstance(knower, str) or knower not in valid_entities or
                         valid_entities[knower]["kind"] != "character"))
                    or (scope != "character_belief" and knower is not None)):
                discarded_invalid += 1
                continue
            key = (item["source_id"], qstart, item["predicate"], who)
            if key not in keys and len(candidates) + len(new) < MAX_STORED_SUGGESTIONS:
                keys.add(key)
                new.append(item)
        candidates.extend(new)
        state = "complete" if stop >= len(content) else "ready"
        con.execute("""UPDATE series_extraction_jobs
            SET status=?,next_offset=?,candidate_json=?,discarded=?,processed_windows=?,
                last_error='',leased_at=NULL,updated_at=?
            WHERE id=? AND status='running'""",
            (state, stop, json.dumps(candidates, ensure_ascii=False),
             fresh["discarded"] + result["discarded"] + discarded_invalid,
             fresh["processed_windows"] + 1, vault.now(), job_id))
        updated = _public(_row(con, series_id, job_id))
        updated["last_window"] = {
            "start": start, "end": stop, "alignment": boundary_kind,
            "author_confirmed_structure": boundary_kind == "author_confirmed_epub_spine",
        }
        return updated
