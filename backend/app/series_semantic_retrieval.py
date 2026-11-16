"""Bounded local semantic retrieval over verified source windows, never entailment."""
from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
import time
from contextlib import closing

import httpx

from . import series_vault as vault

URL = "http://127.0.0.1:11434/api/embed"
MODEL = "qwen3-embedding:4b"
MAX_CANDIDATES = 40
MAX_CACHED_SCAN = 2000
BATCH = 8

_EMBED_LOCK = threading.Lock()
_EMBED_UNAVAILABLE_UNTIL = 0.0
COOLDOWN_SECONDS = 180


def _embed(texts: list[str], model: str) -> list[list[float]]:
    # A fixed loopback endpoint, no proxy, redirects, or remote model names.
    if not re.fullmatch(r"[A-Za-z0-9_.-]+(?::[A-Za-z0-9_.-]+)?", model) or (
            "cloud" in model.casefold()):
        raise ValueError("Local embedding model required")
    with httpx.Client(timeout=httpx.Timeout(10, connect=2), trust_env=False,
                      follow_redirects=False) as client:
        response = client.post(URL, json={"model": model, "input": texts})
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise ValueError("Oversized embedding response")
        return response.json()["embeddings"]


def _vector(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 16384:
        raise ValueError("Invalid embedding")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError("Invalid embedding")
    norm = math.sqrt(sum(x * x for x in value))
    if not math.isfinite(norm) or not norm:
        raise ValueError("Invalid embedding")
    return [x / norm for x in value]


def _path(series_id):
    if not re.fullmatch(r"[0-9a-f]{32}", series_id):
        raise ValueError("Invalid Series Vault identifier")
    return vault._root() / f"semantic-windows-{series_id}.sqlite3"


def retrieve(series_id: str, question: str, candidates: list[dict], *,
             max_book: int, min_book: int = 1, limit: int = 10,
             embed=None, model: str = MODEL) -> dict:
    """Incrementally cache verified candidates and search a bounded cached subset.

    Coverage is only windows previously encountered, not the full source corpus.
    The injected embed callable takes a list of texts and returns vectors.
    """
    if not 1 <= min_book <= max_book <= 9999 or not 1 <= limit <= 50:
        raise ValueError("Invalid retrieval window")
    detail = vault.series_detail(series_id)
    sources = {s["id"]: (v["ordinal"], v["title"], s["sha256"])
               for v in detail["volumes"] for s in v["sources"]}
    snapshots = {}

    def verified(hit):
        source_id = hit.get("source_id")
        info = sources.get(source_id)
        start, end, excerpt = (hit.get("excerpt_start"), hit.get("excerpt_end"),
                               hit.get("excerpt"))
        if (not info or type(hit.get("book")) is not int or hit["book"] != info[0]
                or not min_book <= info[0] <= max_book or type(start) is not int
                or type(end) is not int or start < 0 or not isinstance(excerpt, str)
                or not excerpt or len(excerpt) > 1150 or end != start + len(excerpt)):
            return None
        if source_id not in snapshots:
            try:
                snapshots[source_id] = vault.source_text(series_id, source_id)[1]
            except (OSError, ValueError):
                snapshots[source_id] = None
        text = snapshots[source_id]
        if text is None or text[start:end] != excerpt:
            return None
        return {"book": info[0], "volume": info[1], "source_id": source_id,
                "excerpt_start": start, "excerpt_end": end, "excerpt": excerpt}

    valid = []
    seen = set()
    for hit in candidates[:MAX_CANDIDATES]:
        row = verified(hit)
        if row:
            key = (row["source_id"], row["excerpt_start"], row["excerpt_end"])
            if key not in seen:
                seen.add(key)
                valid.append(row)
    global _EMBED_UNAVAILABLE_UNTIL
    local_request = embed is None
    if local_request:
        with _EMBED_LOCK:
            cooling_down = time.monotonic() < _EMBED_UNAVAILABLE_UNTIL
        if cooling_down:
            return {"results": valid[:limit], "status": "embedding_model_cooldown",
                    "cached_scanned": 0,
                    "coverage": "incremental_windows_only",
                    "semantic_entailment": "unverified"}
    embed = embed or (lambda texts: _embed(texts, model))
    status = "semantic_unavailable"
    try:
        with closing(sqlite3.connect(_path(series_id), timeout=2)) as con:
            con.execute("CREATE TABLE IF NOT EXISTS windows (model TEXT, source_id TEXT, "
                        "source_hash TEXT, start INTEGER, end INTEGER, vector TEXT, "
                        "PRIMARY KEY(model,source_id,source_hash,start,end))")
            query_vectors = embed([question])
            if len(query_vectors) != 1:
                raise ValueError("Invalid embedding count")
            query_vector = _vector(query_vectors[0])
            missing = []
            for row in valid:
                key = (model, row["source_id"], sources[row["source_id"]][2],
                       row["excerpt_start"], row["excerpt_end"])
                if not con.execute("SELECT 1 FROM windows WHERE model=? AND source_id=? "
                                   "AND source_hash=? AND start=? AND end=?", key).fetchone():
                    missing.append((key, row))
            for offset in range(0, len(missing), BATCH):
                batch = missing[offset:offset + BATCH]
                vectors = embed([row["excerpt"] for _, row in batch])
                if len(vectors) != len(batch):
                    raise ValueError("Invalid embedding count")
                for (key, _), vector in zip(batch, vectors):
                    vector = _vector(vector)
                    if len(vector) != len(query_vector):
                        raise ValueError("Embedding dimension mismatch")
                    con.execute("INSERT OR REPLACE INTO windows VALUES (?,?,?,?,?,?)",
                                (*key, json.dumps(vector)))
                con.commit()
            # Stable bounded scan; old or changed sources are excluded before use.
            cached = con.execute("SELECT source_id,source_hash,start,end,vector FROM windows "
                                 "WHERE model=? ORDER BY source_id,start,end LIMIT ?",
                                 (model, MAX_CACHED_SCAN)).fetchall()
            scored = []
            for source_id, source_hash, start, end, encoded in cached:
                info = sources.get(source_id)
                if not info or info[2] != source_hash or not min_book <= info[0] <= max_book:
                    continue
                if source_id not in snapshots:
                    try:
                        snapshots[source_id] = vault.source_text(series_id, source_id)[1]
                    except (OSError, ValueError):
                        snapshots[source_id] = None
                text = snapshots[source_id]
                if (text is None or start < 0 or end <= start or end > len(text)
                        or end - start > 1150):
                    continue
                row = verified({"book": info[0], "source_id": source_id,
                                "excerpt_start": start, "excerpt_end": end,
                                "excerpt": text[start:end]})
                try:
                    vector = _vector(json.loads(encoded))
                    if len(vector) != len(query_vector):
                        continue
                except (ValueError, TypeError):
                    continue
                score = sum(a * b for a, b in zip(query_vector, vector))
                scored.append((score, row))
            scored.sort(key=lambda item: (-item[0], item[1]["book"],
                                           item[1]["source_id"], item[1]["excerpt_start"]))
            # Round-robin volumes, starting with the strongest matching volume.
            groups = {}
            for score, row in scored:
                groups.setdefault(row["book"], []).append((score, row))
            ranked = []
            while groups and len(ranked) < limit:
                for book in list(groups):
                    ranked.append(groups[book].pop(0)[1])
                    if not groups[book]:
                        del groups[book]
                    if len(ranked) == limit:
                        break
            status = "partial_cached_windows"
            if local_request:
                with _EMBED_LOCK:
                    _EMBED_UNAVAILABLE_UNTIL = 0.0
            return {"results": ranked, "status": status, "cached_scanned": len(cached),
                    "coverage": "incremental_windows_only", "semantic_entailment": "unverified"}
    except (httpx.HTTPError, OSError, sqlite3.Error, ValueError, TypeError, KeyError,
            IndexError, OverflowError):
        if local_request:
            with _EMBED_LOCK:
                _EMBED_UNAVAILABLE_UNTIL = time.monotonic() + COOLDOWN_SECONDS
        return {"results": valid[:limit], "status": status, "cached_scanned": 0,
                "coverage": "incremental_windows_only", "semantic_entailment": "unverified"}
