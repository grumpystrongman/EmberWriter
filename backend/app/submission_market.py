"""Local directory snapshots of publishers' official submission rules."""
import asyncio
import csv
import json
import logging
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from http.client import HTTPException
from pathlib import Path

from . import storage
from .submission_guidelines import discover_guidelines, extract_guidelines, fetch_html

LOGGER = logging.getLogger(__name__)
PUBLISHERS = {
    "Fenn & Fable": "https://fennandfable.com/pages/submit",
    "Angry Robot": "https://angryrobotbooks.com/submissions/",
    "Baen Books": "https://www.baen.com/submit",
    "Dzanc Books": "https://www.dzancbooks.org/general-submissions",
    "Graywolf Press": "https://books-events.graywolfpress.org/about-us/submissions",
    "Tor Publishing Group": "https://us.macmillan.com/torpublishinggroup/about/faq/",
    "Asteria Press": "https://www.asteriapress.com/submissions-guidelines",
    "Dark Brew Press": "https://www.darkbrewpress.com/submissions",
    "New Cross Press": "https://newcrosspress.com/submissions",
    "Ransom Publishing": "https://ransomlit.com/submissions/",
    "Rowan Prose Publishing": "https://www.rowanprosepublishing.com/submissions",
}


@lru_cache(maxsize=1)
def book_publisher_catalog() -> list[dict]:
    resources = Path(__file__).with_name("resources")
    entries = []
    for shard in sorted(resources.glob("book-publishers-*.csv")):
        with shard.open(encoding="utf-8", newline="") as source:
            entries.extend(csv.DictReader(source))
    return entries


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
        db.execute("CREATE TABLE IF NOT EXISTS watched_publishers (url TEXT PRIMARY KEY, name TEXT NOT NULL)")
        db.execute("""
            CREATE TABLE IF NOT EXISTS publisher_discovery (
                publisher_id TEXT PRIMARY KEY,
                checked_at TEXT NOT NULL,
                candidate_count INTEGER NOT NULL
            )
        """)
    return db


def watch_publisher(name: str, url: str, guidelines: dict) -> None:
    with closing(_connect()) as db, db:
        db.execute("INSERT OR IGNORE INTO watched_publishers VALUES (?, ?)", (url, name))
        db.execute(
            "INSERT OR IGNORE INTO publisher_rules VALUES (?, ?, ?, NULL, NULL)",
            (url, json.dumps(guidelines, sort_keys=True), storage.utc_now()),
        )


def _sources(db: sqlite3.Connection) -> dict[str, str]:
    sources = {url: name for name, url in PUBLISHERS.items()}
    sources.update({row["url"]: row["name"] for row in db.execute("SELECT * FROM watched_publishers")})
    return sources


@lru_cache(maxsize=1)
def publisher_packs() -> dict:
    path = Path(__file__).with_name("resources") / "publisher-packs.json"
    return json.loads(path.read_text(encoding="utf-8"))


def market_listings() -> list[dict]:
    with closing(_connect()) as db:
        sources = _sources(db)
        snapshots = {row["url"]: dict(row) for row in db.execute("SELECT * FROM publisher_rules")}
    listings = []
    for url, name in sources.items():
        record = snapshots.get(url, {})
        bundled = publisher_packs().get(name, {})
        changed = bool(record.get("changed_at"))
        settings = bundled.get("settings") if not changed else None
        reason = bundled.get("reason") or "Packet requirements still need verification."
        if changed:
            reason = "Publisher rules changed. Compare the current source before using the bundled settings."
        guidelines = json.loads(record["snapshot"]) if record.get("snapshot") else None
        if settings and bundled.get("rules"):
            guidelines = {"text": bundled["rules"], "settings": settings}
        elif guidelines is None and bundled.get("rules"):
            guidelines = {"text": bundled["rules"], "settings": {}}
        listings.append({
            "name": name,
            "url": url,
            "checked_at": record.get("checked_at"),
            "changed_at": record.get("changed_at"),
            "error": record.get("error"),
            "guidelines": guidelines,
            "genres": bundled.get("genres", []),
            "access": bundled.get("access", "unknown"),
            "pack_status": "ready" if settings else "review",
            "pack_reason": None if settings else reason,
        })
    return listings


def refresh_due_publishers() -> None:
    cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    with closing(_connect()) as db:
        for url, name in _sources(db).items():
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


def discover_due_publishers(limit: int = 12) -> None:
    """Discover candidate submission pages in bounded batches across the catalog."""
    cutoff = (datetime.now(UTC) - timedelta(days=90)).isoformat()
    with closing(_connect()) as db:
        checked = {
            row["publisher_id"] for row in db.execute(
                "SELECT publisher_id FROM publisher_discovery WHERE checked_at >= ?", (cutoff,),
            )
        }
        sources = {name.casefold() for name in _sources(db).values()}
        due = [
            publisher for publisher in book_publisher_catalog()
            if publisher["website"] and publisher["wikidata_id"] not in checked
            and publisher["name"].casefold() not in sources
        ]
        for publisher in due[:limit]:
            try:
                candidates = discover_guidelines(publisher["website"])
            except (OSError, ValueError, HTTPException):
                candidates = []
            with db:
                for candidate in candidates:
                    url = candidate["url"]
                    snapshot = {key: candidate[key] for key in ("text", "settings")}
                    db.execute("INSERT OR IGNORE INTO watched_publishers VALUES (?, ?)", (url, publisher["name"]))
                    db.execute(
                        "INSERT OR IGNORE INTO publisher_rules VALUES (?, ?, ?, NULL, NULL)",
                        (url, json.dumps(snapshot, sort_keys=True), storage.utc_now()),
                    )
                db.execute(
                    "INSERT OR REPLACE INTO publisher_discovery VALUES (?, ?, ?)",
                    (publisher["wikidata_id"], storage.utc_now(), len(candidates)),
                )


async def market_refresh_loop() -> None:
    await asyncio.sleep(20)
    while True:
        try:
            await asyncio.to_thread(refresh_due_publishers)
            await asyncio.to_thread(discover_due_publishers)
        except sqlite3.Error:
            LOGGER.exception("Publisher directory refresh failed")
        await asyncio.sleep(60 * 60)
