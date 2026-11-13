"""Private full-series evidence search: exact text, offsets, and temporal book filter.

A local SQLite FTS5 index of immutable source snapshots. Search results are
verifiable quotations, NOT automated canon or psychological inferences.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from . import series_vault as vault

_INDEX_LOCK = threading.Lock()
CHUNK_CHARS = 1150
CHUNK_OVERLAP = 100
MAX_SEARCH_RESULTS = 50


def _index_path(series_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", series_id):
        raise ValueError("Invalid Series Vault identifier")
    return vault._root() / f"source-evidence-{series_id}.sqlite3"


def _signature(series: dict) -> str:
    details = [
        (volume["id"], volume["ordinal"], volume["title"], source["id"],
         source["sha256"], source["sequence"])
        for volume in series["volumes"]
        for source in volume["sources"]
    ]
    return hashlib.sha256(
        json.dumps(details, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _chunks(text: str):
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))
        if end < len(text):
            whitespace = [text.rfind(ch, start + 650, end) for ch in (" ", "\n", "\r", "\t")]
            cut = max(whitespace)
            if cut > start + 650:
                end = cut + 1
        yield start, text[start:end]
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)


def _index_valid(path: Path, signature: str) -> bool:
    if not path.is_file():
        return False
    try:
        with closing(sqlite3.connect(path, timeout=15)) as connection:
            row = connection.execute("SELECT value FROM meta WHERE key='signature'").fetchone()
            return bool(row and row[0] == signature)
    except (sqlite3.DatabaseError, OSError):
        return False


def _build(series: dict, signature: str) -> Path:
    target = _index_path(series["id"])
    if _index_valid(target, signature):
        return target
    with _INDEX_LOCK:
        if _index_valid(target, signature):
            return target
        stage = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            with closing(sqlite3.connect(stage, timeout=30)) as connection:
                connection.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                connection.execute(
                    "CREATE VIRTUAL TABLE chunks USING fts5("
                    "book UNINDEXED, volume UNINDEXED, source_id UNINDEXED,"
                    "source_start UNINDEXED, content, tokenize='unicode61')"
                )
                chunk_count = 0
                for volume in series["volumes"]:
                    for source in volume["sources"]:
                        _, content = vault.source_text(series["id"], source["id"])
                        rows = (
                            (str(volume["ordinal"]), volume["title"], source["id"],
                             str(start), excerpt)
                            for start, excerpt in _chunks(content)
                        )
                        connection.executemany(
                            "INSERT INTO chunks(book,volume,source_id,source_start,content) "
                            "VALUES (?,?,?,?,?)", rows
                        )
                        chunk_count += (len(content) // (CHUNK_CHARS - CHUNK_OVERLAP)) + 1
                connection.execute("INSERT INTO meta VALUES (?,?)", ("signature", signature))
                connection.execute("INSERT INTO meta VALUES (?,?)", ("source_count", str(
                    sum(len(volume["sources"]) for volume in series["volumes"])
                )))
                connection.execute("INSERT INTO meta VALUES (?,?)", ("estimated_chunks", str(chunk_count)))
                connection.commit()
            os.replace(stage, target)
        finally:
            stage.unlink(missing_ok=True)
    return target


def search(series_id: str, query: str, *, min_book: int = 1,
           max_book: int = 9999, limit: int = 20) -> dict:
    query = query.strip()
    if not 2 <= len(query) <= 120:
        raise ValueError("Search query must contain 2–120 characters")
    if not (1 <= min_book <= max_book <= 9999):
        raise ValueError("Invalid search book window")
    if not (1 <= limit <= MAX_SEARCH_RESULTS):
        raise ValueError(f"Choose 1–{MAX_SEARCH_RESULTS} results")
    tokens = re.findall(r"[\w]{2,}", query, re.UNICODE)[:12]
    if not tokens:
        raise ValueError("Search for a character, location, object, or phrase")
    series = vault.series_detail(series_id)
    if not series["volumes"]:
        return {"results": [], "total_hits": 0, "sources": 0, "books": 0,
                "indexed": True, "query": query, "min_book": min_book,
                "max_book": max_book}
    signature = _signature(series)
    index = _build(series, signature)
    # Only quoted tokens and AND operators enter MATCH, never raw user syntax.
    expression = " AND ".join('"' + token.replace('"', '""') + '"' for token in tokens)
    with closing(sqlite3.connect(index, timeout=30)) as connection:
        rows = connection.execute(
            "SELECT book,volume,source_id,source_start,content,bm25(chunks) AS score "
            "FROM chunks WHERE chunks MATCH ? AND CAST(book AS INTEGER) BETWEEN ? AND ? "
            "ORDER BY score LIMIT ?", (expression, min_book, max_book, limit)
        ).fetchall()
        total_hits = connection.execute(
            "SELECT COUNT(*) FROM chunks WHERE chunks MATCH ? "
            "AND CAST(book AS INTEGER) BETWEEN ? AND ?",
            (expression, min_book, max_book)
        ).fetchone()[0]
    findings = []
    for book, volume, source_id, source_start, content, score in rows:
        # Text position is an exact coordinate into the preserved source.
        # Chunks overlap to avoid splitting boundary phrases.
        lowered = content.casefold()
        at = lowered.find(tokens[0].casefold())
        at = max(at, 0)
        left = max(0, at - 120)
        right = min(len(content), at + 300)
        findings.append({
            "book": int(book), "volume": volume,
            "source_id": source_id,
            "excerpt_start": int(source_start) + left,
            "excerpt_end": int(source_start) + right,
            "excerpt": content[left:right],
        })
    return {
        "series_id": series_id, "query": query,
        "min_book": min_book, "max_book": max_book,
        "books": len(series["volumes"]),
        "sources": sum(len(v["sources"]) for v in series["volumes"]),
        "total_hits": total_hits,
        "results": findings,
        "indexed": True,
        "disclaimer": "Literal source matches only. Mentions do not establish motives, events, or approved canon.",
    }


def character_evidence_map(series_id: str, entity_id: str, *,
                           max_book: int = 9999) -> dict:
    """Safe, source-only trajectory. A mention is NOT a story event or motive."""
    if not 1 <= max_book <= 9999:
        raise ValueError("Choose a valid reading position")
    from . import series_canon

    series = vault.series_detail(series_id)
    entity = next((person for person in series_canon.list_entities(series_id)
                   if person["id"] == entity_id and person["kind"] == "character"),
                  None)
    if entity is None:
        raise FileNotFoundError("Character is not part of this Series Vault")
    aliases = []
    for label in [entity["name"], *entity["aliases"]]:
        terms = re.findall(r"[\w]{2,}", label, re.UNICODE)[:5]
        if terms:
            phrase = " ".join(terms)
            if phrase.casefold() not in {word.casefold() for word in aliases}:
                aliases.append(phrase)
        if len(aliases) >= 12:
            break
    volumes = [volume for volume in series["volumes"]
               if volume["ordinal"] <= max_book]
    if not volumes or not aliases:
        return {"series_id": series_id, "entity_id": entity_id,
                "name": entity["name"], "query": entity["name"], "max_book": max_book,
                "total_windows": 0, "first_attested_book": None, "books": [],
                "disclaimer": "Mentions are not proof of psychology, agency or character growth."}
    expression = " OR ".join(
        '"' + alias.replace('"', '""') + '"' for alias in aliases
    )
    index = _build(series, _signature(series))
    with closing(sqlite3.connect(index, timeout=30)) as connection:
        counts = {
            int(book): int(count)
            for book, count in connection.execute(
                "SELECT CAST(book AS INTEGER), COUNT(*) FROM chunks "
                "WHERE chunks MATCH ? AND CAST(book AS INTEGER) <= ? "
                "GROUP BY CAST(book AS INTEGER)", (expression, max_book))
        }
    results = [{
        "book": volume["ordinal"], "title": volume["title"],
        "matching_windows": counts.get(volume["ordinal"], 0),
    } for volume in volumes]
    first = next((volume["book"] for volume in results
                  if volume["matching_windows"] > 0), None)
    return {
        "series_id": series_id, "entity_id": entity_id,
        "name": entity["name"], "query": min(aliases, key=lambda label: (len(label.split()), len(label))),
        "max_book": max_book, "total_windows": sum(counts.values()),
        "first_attested_book": first, "books": results,
        "disclaimer": "Literal matching source windows, including possible overlapping windows. A mention alone cannot establish a character's feelings, motives, relationships or story events. Approval is always required for canon.",
    }
