"""Durable author-operated multi-source extraction cursor.

Every POST /next processes at most one 1,400-character source window.
No background jobs, remote fallback, manuscript writes, or canon approval.
The underlying per-source extraction job is idempotently recovered if a batch
request is interrupted after the model commits its source checkpoint.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime, timedelta

from . import series_extraction_jobs as extraction
from . import series_model_readiness as readiness
from . import series_vault as vault

MAX_SOURCES = 80
LEASE_SECONDS = 150


def _ensure(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS series_extraction_batches (
          id TEXT PRIMARY KEY,
          series_id TEXT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
          model TEXT NOT NULL,
          source_plan_json TEXT NOT NULL,
          source_cursor INTEGER NOT NULL DEFAULT 0,
          processed_windows INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'ready',
          leased_at TEXT,
          last_error TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          CHECK(status IN ('ready','running','pause_requested','paused','error','complete','cancelled'))
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS extraction_batches_series_idx "
                "ON series_extraction_batches(series_id,created_at)")


def _row(con: sqlite3.Connection, series_id: str, batch_id: str) -> dict:
    row = con.execute(
        "SELECT * FROM series_extraction_batches WHERE id=? AND series_id=?",
        (batch_id, series_id),
    ).fetchone()
    if row is None:
        raise FileNotFoundError("Series extraction batch not found")
    return dict(row)


def _public(row: dict) -> dict:
    plan = json.loads(row["source_plan_json"])
    return {
        "id": row["id"], "series_id": row["series_id"], "model": row["model"],
        "source_count": len(plan), "current_source_index": row["source_cursor"],
        "processed_windows": row["processed_windows"], "status": row["status"],
        "error": row["last_error"], "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "auto_canon_approved": False, "source_text_sent_remotely": False,
        "execution_mode": "manual_single_window_across_sources",
        "source_ids": [item["source_id"] for item in plan],
    }


def create(series_id: str, model: str, book_from: int, book_to: int) -> dict:
    model = model.strip()
    if not 1 <= book_from <= book_to <= 9999:
        raise ValueError("Choose a valid consecutive book range")
    if not 1 <= len(model) <= 200 or any(ch in model for ch in "\n\r\x00"):
        raise ValueError("Choose an installed local Ollama model")
    available = readiness.model_readiness(series_id)
    if available["status"] != "available" or model not in available["models"]:
        raise ValueError("Choose a currently installed local Ollama model")
    detail = vault.series_detail(series_id)
    plan = [
        {"source_id": source["id"], "sha256": source["sha256"],
         "book": volume["ordinal"]}
        for volume in detail["volumes"]
        if book_from <= volume["ordinal"] <= book_to
        for source in volume["sources"]
    ]
    if not 1 <= len(plan) <= MAX_SOURCES:
        raise ValueError("Select between 1 and 80 imported sources per batch")
    stamp = vault.now()
    identifier = vault._id()
    with vault._connect() as con:
        _ensure(con)
        con.execute("""
            INSERT INTO series_extraction_batches
             (id,series_id,model,source_plan_json,source_cursor,
              processed_windows,status,created_at,updated_at)
            VALUES (?,?,?,?,0,0,'ready',?,?)
        """, (identifier, series_id, model, json.dumps(plan), stamp, stamp))
        return _public(_row(con, series_id, identifier))


def get(series_id: str, batch_id: str) -> dict:
    vault.series_detail(series_id)
    with vault._connect() as con:
        _ensure(con)
        return _public(_row(con, series_id, batch_id))


def list_batches(series_id: str) -> list[dict]:
    vault.series_detail(series_id)
    with vault._connect() as con:
        _ensure(con)
        rows = con.execute(
            "SELECT * FROM series_extraction_batches WHERE series_id=? "
            "ORDER BY created_at DESC LIMIT 20", (series_id,),
        ).fetchall()
        return [_public(dict(row)) for row in rows]


def pause(series_id: str, batch_id: str) -> dict:
    with vault._connect() as con:
        _ensure(con)
        row = _row(con, series_id, batch_id)
        if row["status"] in ("complete", "cancelled"):
            return _public(row)
        state = "pause_requested" if row["status"] == "running" else "paused"
        con.execute("UPDATE series_extraction_batches SET status=?,updated_at=? "
                    "WHERE id=?", (state, vault.now(), batch_id))
        return _public(_row(con, series_id, batch_id))


def resume(series_id: str, batch_id: str) -> dict:
    with vault._connect() as con:
        _ensure(con)
        row = _row(con, series_id, batch_id)
        if row["status"] not in ("paused", "error"):
            raise ValueError("Only paused or failed batches can resume")
        con.execute("UPDATE series_extraction_batches SET status='ready',"
                    "last_error='',updated_at=? WHERE id=?", (vault.now(), batch_id))
        return _public(_row(con, series_id, batch_id))


def cancel(series_id: str, batch_id: str) -> dict:
    with vault._connect() as con:
        _ensure(con)
        row = _row(con, series_id, batch_id)
        if row["status"] == "running":
            con.execute("UPDATE series_extraction_batches SET status='pause_requested',"
                        "updated_at=? WHERE id=?", (vault.now(), batch_id))
        elif row["status"] != "complete":
            con.execute("UPDATE series_extraction_batches SET status='cancelled',"
                        "updated_at=? WHERE id=?", (vault.now(), batch_id))
        return _public(_row(con, series_id, batch_id))


async def advance(series_id: str, batch_id: str) -> dict:
    with vault._connect() as con:
        _ensure(con)
        row = _row(con, series_id, batch_id)
        if row["status"] == "complete":
            return _public(row)
        if row["status"] != "ready":
            if row["status"] == "running":
                try:
                    leased = datetime.fromisoformat(row["leased_at"])
                except (TypeError, ValueError):
                    leased = datetime.min.replace(tzinfo=UTC)
                if datetime.now(UTC) - leased >= timedelta(seconds=LEASE_SECONDS):
                    con.execute(
                        "UPDATE series_extraction_batches SET status='ready',leased_at=NULL "
                        "WHERE id=? AND status='running'", (batch_id,),
                    )
                else:
                    raise ValueError("Batch window already running")
            else:
                raise ValueError("Batch is paused, cancelled or requires explicit resume")
        claimed = con.execute(
            "UPDATE series_extraction_batches SET status='running',leased_at=?,updated_at=? "
            "WHERE id=? AND status='ready'",
            (vault.now(), vault.now(), batch_id),
        )
        if claimed.rowcount != 1:
            raise ValueError("Batch already advancing")
        row = _row(con, series_id, batch_id)
        plan = json.loads(row["source_plan_json"])
        cursor = row["source_cursor"]
        if cursor >= len(plan):
            con.execute(
                "UPDATE series_extraction_batches SET status='complete' WHERE id=?",
                (batch_id,),
            )
            return _public(_row(con, series_id, batch_id))
        selection = plan[cursor]

    try:
        source, _ = vault.source_text(series_id, selection["source_id"])
        if source["sha256"] != selection["sha256"]:
            raise ValueError("Source fingerprint changed; batch requires author review")
        job = extraction.create(series_id, selection["source_id"], row["model"])
        if job["status"] not in ("complete",):
            job = await extraction.advance(series_id, job["id"])
    except asyncio.CancelledError:
        with vault._connect() as con:
            _ensure(con)
            con.execute("UPDATE series_extraction_batches SET status='paused',"
                        "leased_at=NULL,last_error='Interrupted safely',updated_at=? "
                        "WHERE id=? AND status IN ('running','pause_requested')",
                        (vault.now(), batch_id))
        raise
    except Exception:
        with vault._connect() as con:
            _ensure(con)
            con.execute(
                "UPDATE series_extraction_batches SET status='error',"
                "last_error=?,leased_at=NULL,updated_at=? WHERE id=? "
                "AND status IN ('running','pause_requested')",
                ("Local source window failed; review the model and resume", vault.now(), batch_id),
            )
        raise

    with vault._connect() as con:
        _ensure(con)
        current = _row(con, series_id, batch_id)
        if current["status"] not in ("running", "pause_requested"):
            raise ValueError("Batch state changed; source checkpoint remains intact")
        next_cursor = cursor + (job["status"] == "complete")
        done = next_cursor >= len(plan)
        status = ("complete" if done else
                  "paused" if current["status"] == "pause_requested" else "ready")
        con.execute("""
            UPDATE series_extraction_batches
            SET status=?,source_cursor=?,processed_windows=?,
                leased_at=NULL,last_error='',updated_at=? WHERE id=?
        """, (status, next_cursor, row["processed_windows"] + 1,
              vault.now(), batch_id))
        result = _public(_row(con, series_id, batch_id))
        result["last_source"] = {
            "source_id": selection["source_id"], "book": selection["book"],
            "processed_windows": job["processed_windows"],
            "source_progress_percent": job["progress_percent"],
            "candidate_count": job["candidate_count"],
            "all_candidates_unapproved": True,
        }
        return result
