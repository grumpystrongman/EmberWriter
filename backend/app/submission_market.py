"""Local directory snapshots of publishers' official submission rules."""
import asyncio
import json
import logging
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from http.client import HTTPException

from . import storage
from .submission_guidelines import extract_guidelines, fetch_html

LOGGER = logging.getLogger(__name__)
PUBLISHERS = {
    "Fenn & Fable": "https://fennandfable.com/pages/submit",
    "Asteria Press": "https://www.asteriapress.com/submissions-guidelines",
    "Dark Brew Press": "https://www.darkbrewpress.com/submissions",
    "New Cross Press": "https://newcrosspress.com/submissions",
    "Ransom Publishing": "https://ransomlit.com/submissions/",
    "Rowan Prose Publishing": "https://www.rowanprosepublishing.com/submissions",
}


def _connect() -> sqlite3.Connection:
    storage.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(storage.DATA_ROOT / "submission-market.sqlite3")
    db.row_factory = sqlite3.Row
    with db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS publisher_rules (
                url TEXT PRIMARY KEY,
                snapshot TEXT,
                checked_at TEXT,
                changed_at TEXT,
                error TEXT
            )
        """)
    return db


def market_listings() -> list[dict]:
    with closing(_connect()) as db:
        snapshots = {row["url"]: dict(row) for row in db.execute("SELECT * FROM publisher_rules")}
    listings = []
    for name, url in PUBLISHERS.items():
        record = snapshots.get(url, {})
        listings.append({
            "name": name,
            "url": url,
            "checked_at": record.get("checked_at"),
            "changed_at": record.get("changed_at"),
            "error": record.get("error"),
            "guidelines": json.loads(record["snapshot"]) if record.get("snapshot") else None,
        })
    return listings


def refresh_due_publishers() -> None:
    cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    with closing(_connect()) as db:
        for name, url in PUBLISHERS.items():
            previous = db.execute("SELECT * FROM publisher_rules WHERE url = ?", (url,)).fetchone()
            if previous and previous["checked_at"] >= cutoff:
                continue
            checked_at = storage.utc_now()
            snapshot = previous["snapshot"] if previous else None
            changed_at = previous["changed_at"] if previous else None
            error = None
            try:
                fresh = json.dumps(extract_guidelines(fetch_html(url)), sort_keys=True)
                if snapshot is not None and fresh != snapshot:
                    changed_at = checked_at
                snapshot = fresh
            except (OSError, ValueError, HTTPException):
                error = "Latest check failed. Open the official page to verify current rules."
                LOGGER.info("Publisher guidelines check failed for %s", name)
            with db:
                db.execute(
                    "INSERT OR REPLACE INTO publisher_rules VALUES (?, ?, ?, ?, ?)",
                    (url, snapshot, checked_at, changed_at, error),
                )


async def market_refresh_loop() -> None:
    await asyncio.sleep(20)
    while True:
        try:
            await asyncio.to_thread(refresh_due_publishers)
        except sqlite3.Error:
            LOGGER.exception("Publisher directory refresh failed")
        await asyncio.sleep(60 * 60)
