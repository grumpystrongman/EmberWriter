from __future__ import annotations

import asyncio
import hashlib
import io
import json
import math
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from . import storage
from .generation import generate
from .knowledge_models import (
    EmbeddingConfig,
    GrammarIssue,
    GrammarReviewRequest,
    KnowledgeAnswerRequest,
    KnowledgeSearchRequest,
)

SOURCE_FILE = Path(__file__).with_name("knowledge_sources.json")
SEED_FILE = Path(__file__).with_name("knowledge_seed.json")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _db_path() -> Path:
    storage.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    return storage.DATA_ROOT / "knowledge.db"


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path())
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_sources (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            authority TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            refresh_days INTEGER NOT NULL,
            last_checked_at TEXT,
            last_success_at TEXT,
            content_hash TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT ''
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            checked_at TEXT,
            content_hash TEXT NOT NULL,
            FOREIGN KEY(source_id) REFERENCES knowledge_sources(id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_embeddings (
            chunk_id TEXT NOT NULL,
            model TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            vector_json TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY(chunk_id, model)
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_source ON knowledge_chunks(source_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_category ON knowledge_chunks(category)")
    try:
        con.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                chunk_id UNINDEXED,
                source_id UNINDEXED,
                category UNINDEXED,
                authority,
                source_title,
                title,
                body
            )
            """
        )
    except sqlite3.OperationalError:
        pass
    con.commit()
    return con


def _load_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError(f"Knowledge manifest must be a list: {path.name}")
    return [item for item in payload if isinstance(item, dict)]


def _source_manifest() -> list[dict[str, Any]]:
    return _load_json(SOURCE_FILE)


def _seed_rules() -> list[dict[str, Any]]:
    return _load_json(SEED_FILE)


def _reindex_chunk(con: sqlite3.Connection, chunk_id: str) -> None:
    row = con.execute(
        """
        SELECT c.*, s.authority, s.title AS source_title
        FROM knowledge_chunks c JOIN knowledge_sources s ON s.id = c.source_id
        WHERE c.id = ?
        """,
        (chunk_id,),
    ).fetchone()
    if row is None:
        return
    try:
        con.execute("DELETE FROM knowledge_fts WHERE chunk_id = ?", (chunk_id,))
        con.execute(
            """
            INSERT INTO knowledge_fts
            (chunk_id, source_id, category, authority, source_title, title, body)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["source_id"],
                row["category"],
                row["authority"],
                row["source_title"],
                row["title"],
                row["body"],
            ),
        )
    except sqlite3.OperationalError:
        return


def ensure_seeded() -> None:
    manifest = {item["id"]: item for item in _source_manifest() if item.get("id")}
    seeds = _seed_rules()
    seed_checked: dict[str, str] = {}
    for rule in seeds:
        source_id = str(rule.get("source_id", ""))
        checked = str(rule.get("checked_at", ""))
        if source_id and checked and checked > seed_checked.get(source_id, ""):
            seed_checked[source_id] = checked

    with _connect() as con:
        for source in manifest.values():
            con.execute(
                """
                INSERT INTO knowledge_sources
                (id, category, authority, title, url, refresh_days, last_checked_at, last_success_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    category=excluded.category,
                    authority=excluded.authority,
                    title=excluded.title,
                    url=excluded.url,
                    refresh_days=excluded.refresh_days
                """,
                (
                    source["id"],
                    source["category"],
                    source["authority"],
                    source["title"],
                    source["url"],
                    int(source.get("refresh_days", 30)),
                    seed_checked.get(source["id"]),
                    seed_checked.get(source["id"]),
                ),
            )
        live_source_ids = {
            row["id"]
            for row in con.execute(
                "SELECT id FROM knowledge_sources WHERE content_hash <> ''"
            ).fetchall()
        }
        for rule in seeds:
            source_id = str(rule.get("source_id", ""))
            source = manifest.get(source_id)
            if source is None or source_id in live_source_ids:
                continue
            rule_id = str(rule.get("id", "")).strip()
            body = str(rule.get("body", "")).strip()
            title = str(rule.get("title", "")).strip()
            if not rule_id or not body or not title:
                continue
            existing = con.execute("SELECT 1 FROM knowledge_chunks WHERE id = ?", (rule_id,)).fetchone()
            if existing:
                continue
            con.execute(
                """
                INSERT INTO knowledge_chunks
                (id, source_id, category, title, body, checked_at, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule_id,
                    source_id,
                    source["category"],
                    title,
                    body,
                    rule.get("checked_at"),
                    _digest(body),
                ),
            )
            _reindex_chunk(con, rule_id)


def _source_state(row: sqlite3.Row, chunks: int) -> dict[str, Any]:
    checked = _parse_time(row["last_checked_at"])
    due = checked is None or datetime.now(UTC) >= checked + timedelta(days=row["refresh_days"])
    if row["error"]:
        status = "error"
    elif checked is None:
        status = "never_checked"
    elif due:
        status = "stale"
    elif row["content_hash"]:
        status = "current"
    else:
        status = "seeded"
    return {
        "id": row["id"],
        "category": row["category"],
        "authority": row["authority"],
        "title": row["title"],
        "url": row["url"],
        "refresh_days": row["refresh_days"],
        "last_checked_at": row["last_checked_at"],
        "last_success_at": row["last_success_at"],
        "content_hash": row["content_hash"],
        "status": status,
        "error": row["error"],
        "chunks": chunks,
    }


def list_sources() -> list[dict[str, Any]]:
    ensure_seeded()
    with _connect() as con:
        rows = con.execute(
            """
            SELECT s.*, COUNT(c.id) AS chunks
            FROM knowledge_sources s
            LEFT JOIN knowledge_chunks c ON c.source_id = s.id
            GROUP BY s.id
            ORDER BY s.category, s.authority, s.title
            """
        ).fetchall()
    return [_source_state(row, int(row["chunks"])) for row in rows]


def _extract_html(content: bytes) -> str:
    soup = BeautifulSoup(content, "html.parser")
    for element in soup(["script", "style", "svg", "nav", "footer", "header", "noscript"]):
        element.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    blocks: list[str] = []
    for element in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "dt", "dd"]):
        text = re.sub(r"\s+", " ", element.get_text(" ", strip=True)).strip()
        if len(text) >= 20:
            blocks.append(text)
    if not blocks:
        text = re.sub(r"\s+", " ", root.get_text(" ", strip=True)).strip()
        return text
    return "\n\n".join(blocks)


def _extract_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        text = re.sub(r"[ \t]+", " ", text).strip()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def _chunk_text(text: str, max_chars: int = 2200) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text)
    paragraphs = [re.sub(r"\s+", " ", item).strip() for item in re.split(r"\n\s*\n", normalized)]
    paragraphs = [item for item in paragraphs if len(item) >= 20]
    if not paragraphs:
        compact = re.sub(r"\s+", " ", normalized).strip()
        return [compact] if compact else []
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            piece = ""
            for sentence in sentences:
                candidate = f"{piece} {sentence}".strip()
                if len(candidate) > max_chars and piece:
                    chunks.append(piece)
                    piece = sentence
                else:
                    piece = candidate
            if piece:
                chunks.append(piece)
            continue
        candidate = f"{current}\n\n{paragraph}".strip()
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


async def refresh_source(source_id: str) -> dict[str, Any]:
    ensure_seeded()
    with _connect() as con:
        source = con.execute("SELECT * FROM knowledge_sources WHERE id = ?", (source_id,)).fetchone()
    if source is None:
        raise FileNotFoundError(source_id)

    checked_at = _now()
    try:
        timeout = httpx.Timeout(connect=15.0, read=45.0, write=30.0, pool=15.0)
        headers = {"User-Agent": "EmberWriter/0.8 knowledge-refresh"}
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = await client.get(source["url"])
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", "").casefold()
        if source["url"].casefold().endswith(".pdf") or "application/pdf" in content_type:
            extracted = _extract_pdf(content)
        else:
            extracted = _extract_html(content)
        extracted = extracted.strip()
        if len(extracted) < 200:
            raise ValueError("Source returned too little readable text")
        digest = _digest(extracted)
        if digest == source["content_hash"]:
            with _connect() as con:
                con.execute(
                    """
                    UPDATE knowledge_sources
                    SET last_checked_at = ?, last_success_at = ?, error = ''
                    WHERE id = ?
                    """,
                    (checked_at, checked_at, source_id),
                )
            count = source_chunk_count(source_id)
            return {
                "source_id": source_id,
                "status": "unchanged",
                "chunks": count,
                "checked_at": checked_at,
                "error": "",
            }

        chunks = _chunk_text(extracted)
        if not chunks:
            raise ValueError("Source could not be divided into knowledge chunks")
        with _connect() as con:
            old_ids = [
                row["id"]
                for row in con.execute(
                    "SELECT id FROM knowledge_chunks WHERE source_id = ?", (source_id,)
                ).fetchall()
            ]
            for chunk_id in old_ids:
                try:
                    con.execute("DELETE FROM knowledge_fts WHERE chunk_id = ?", (chunk_id,))
                except sqlite3.OperationalError:
                    pass
            con.execute(
                "DELETE FROM knowledge_embeddings "
                "WHERE chunk_id IN (SELECT id FROM knowledge_chunks WHERE source_id = ?)",
                (source_id,),
            )
            con.execute("DELETE FROM knowledge_chunks WHERE source_id = ?", (source_id,))
            for index, body in enumerate(chunks, start=1):
                chunk_id = f"{source_id}:live:{index:04d}"
                title = f"{source['title']} · section {index}"
                con.execute(
                    """
                    INSERT INTO knowledge_chunks
                    (id, source_id, category, title, body, checked_at, content_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        source_id,
                        source["category"],
                        title,
                        body,
                        checked_at,
                        _digest(body),
                    ),
                )
                _reindex_chunk(con, chunk_id)
            con.execute(
                """
                UPDATE knowledge_sources
                SET last_checked_at = ?, last_success_at = ?, content_hash = ?, error = ''
                WHERE id = ?
                """,
                (checked_at, checked_at, digest, source_id),
            )
        return {
            "source_id": source_id,
            "status": "updated",
            "chunks": len(chunks),
            "checked_at": checked_at,
            "error": "",
        }
    except (httpx.HTTPError, OSError, ValueError) as exc:
        with _connect() as con:
            con.execute(
                "UPDATE knowledge_sources SET last_checked_at = ?, error = ? WHERE id = ?",
                (checked_at, str(exc)[:1000], source_id),
            )
        return {
            "source_id": source_id,
            "status": "error",
            "chunks": source_chunk_count(source_id),
            "checked_at": checked_at,
            "error": str(exc),
        }


def source_chunk_count(source_id: str) -> int:
    with _connect() as con:
        row = con.execute(
            "SELECT COUNT(*) AS count FROM knowledge_chunks WHERE source_id = ?", (source_id,)
        ).fetchone()
    return int(row["count"] if row else 0)


def due_source_ids() -> list[str]:
    return [
        source["id"]
        for source in list_sources()
        if source["status"] in {"stale", "never_checked", "error"}
    ]


async def refresh_due_sources(source_ids: list[str] | None = None) -> dict[str, Any]:
    ids = source_ids or due_source_ids()
    semaphore = asyncio.Semaphore(3)

    async def one(source_id: str) -> dict[str, Any]:
        async with semaphore:
            return await refresh_source(source_id)

    results = await asyncio.gather(*(one(source_id) for source_id in ids)) if ids else []
    return {
        "checked": len(results),
        "updated": sum(item["status"] == "updated" for item in results),
        "unchanged": sum(item["status"] == "unchanged" for item in results),
        "failed": sum(item["status"] == "error" for item in results),
        "results": results,
    }


def _fts_query(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]{1,}", query)
    return " OR ".join(f'"{token.replace(chr(34), "")}"' for token in tokens[:24])


def _row_to_chunk(row: sqlite3.Row, score: float = 0.0) -> dict[str, Any]:
    return {
        "id": row["id"],
        "source_id": row["source_id"],
        "category": row["category"],
        "authority": row["authority"],
        "source_title": row["source_title"],
        "source_url": row["url"],
        "title": row["title"],
        "body": row["body"],
        "checked_at": row["checked_at"],
        "score": score,
        "semantic_score": None,
    }


def lexical_search(query: str, categories: list[str], limit: int) -> list[dict[str, Any]]:
    ensure_seeded()
    category_clause = ""
    category_params: list[Any] = []
    if categories:
        placeholders = ",".join("?" for _ in categories)
        category_clause = f" AND c.category IN ({placeholders})"
        category_params.extend(categories)
    with _connect() as con:
        fts = _fts_query(query)
        if fts:
            try:
                rows = con.execute(
                    f"""
                    SELECT c.*, s.authority, s.title AS source_title, s.url,
                           bm25(knowledge_fts) AS rank
                    FROM knowledge_fts
                    JOIN knowledge_chunks c ON c.id = knowledge_fts.chunk_id
                    JOIN knowledge_sources s ON s.id = c.source_id
                    WHERE knowledge_fts MATCH ?{category_clause}
                    ORDER BY rank
                    LIMIT ?
                    """,
                    [fts, *category_params, limit],
                ).fetchall()
                if rows:
                    return [
                        _row_to_chunk(row, score=max(0.0, -float(row["rank"]))) for row in rows
                    ]
            except sqlite3.OperationalError:
                pass
        lowered = f"%{query.casefold()}%"
        rows = con.execute(
            f"""
            SELECT c.*, s.authority, s.title AS source_title, s.url
            FROM knowledge_chunks c JOIN knowledge_sources s ON s.id = c.source_id
            WHERE (lower(c.title) LIKE ? OR lower(c.body) LIKE ?){category_clause}
            ORDER BY c.category, c.title
            LIMIT ?
            """,
            [lowered, lowered, *category_params, limit],
        ).fetchall()
    return [_row_to_chunk(row, score=1.0) for row in rows]


async def _embed(config: EmbeddingConfig, texts: list[str]) -> list[list[float]]:
    if not config.model.strip():
        raise ValueError("Choose an embedding model before semantic indexing/search")
    timeout = httpx.Timeout(connect=15.0, read=180.0, write=60.0, pool=15.0)
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        if config.provider == "ollama":
            response = await client.post(
                f"{config.base_url.rstrip('/')}/api/embed",
                json={"model": config.model, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()
            vectors = payload.get("embeddings", [])
        else:
            base = config.base_url.rstrip("/")
            url = f"{base}/embeddings" if base.endswith("/v1") else f"{base}/v1/embeddings"
            response = await client.post(
                url,
                headers=headers,
                json={"model": config.model, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()
            vectors = [item.get("embedding", []) for item in payload.get("data", [])]
    if len(vectors) != len(texts) or not vectors or not all(isinstance(item, list) for item in vectors):
        raise ValueError("Embedding server returned an invalid vector batch")
    return [[float(value) for value in vector] for vector in vectors]


async def index_embeddings(
    config: EmbeddingConfig, categories: list[str], force: bool
) -> dict[str, Any]:
    ensure_seeded()
    category_clause = ""
    params: list[Any] = []
    if categories:
        placeholders = ",".join("?" for _ in categories)
        category_clause = f"WHERE category IN ({placeholders})"
        params.extend(categories)
    with _connect() as con:
        rows = con.execute(
            f"SELECT id, title, body, content_hash FROM knowledge_chunks {category_clause} ORDER BY id",
            params,
        ).fetchall()
        existing = {
            row["chunk_id"]: row["content_hash"]
            for row in con.execute(
                "SELECT chunk_id, content_hash FROM knowledge_embeddings WHERE model = ?",
                (config.model,),
            ).fetchall()
        }
    pending = [row for row in rows if force or existing.get(row["id"]) != row["content_hash"]]
    indexed = 0
    dimensions = 0
    for start in range(0, len(pending), 16):
        batch = pending[start : start + 16]
        vectors = await _embed(config, [f"{row['title']}\n{row['body']}" for row in batch])
        with _connect() as con:
            for row, vector in zip(batch, vectors, strict=True):
                dimensions = len(vector)
                con.execute(
                    """
                    INSERT INTO knowledge_embeddings
                    (chunk_id, model, dimensions, vector_json, content_hash, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id, model) DO UPDATE SET
                        dimensions=excluded.dimensions,
                        vector_json=excluded.vector_json,
                        content_hash=excluded.content_hash,
                        created_at=excluded.created_at
                    """,
                    (
                        row["id"],
                        config.model,
                        len(vector),
                        json.dumps(vector),
                        row["content_hash"],
                        _now(),
                    ),
                )
                indexed += 1
    if not pending:
        with _connect() as con:
            row = con.execute(
                "SELECT dimensions FROM knowledge_embeddings WHERE model = ? LIMIT 1",
                (config.model,),
            ).fetchone()
        dimensions = int(row["dimensions"]) if row else 0
    return {"model": config.model, "chunks_indexed": indexed, "dimensions": dimensions}


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


async def search_knowledge(request: KnowledgeSearchRequest) -> list[dict[str, Any]]:
    lexical = lexical_search(request.query, request.categories, max(request.limit * 2, 20))
    if not request.semantic or request.embedding is None or not request.embedding.model.strip():
        return lexical[: request.limit]
    query_vector = (await _embed(request.embedding, [request.query]))[0]
    category_clause = ""
    params: list[Any] = [request.embedding.model]
    if request.categories:
        placeholders = ",".join("?" for _ in request.categories)
        category_clause = f" AND c.category IN ({placeholders})"
        params.extend(request.categories)
    with _connect() as con:
        rows = con.execute(
            f"""
            SELECT e.vector_json, c.*, s.authority, s.title AS source_title, s.url
            FROM knowledge_embeddings e
            JOIN knowledge_chunks c ON c.id = e.chunk_id
            JOIN knowledge_sources s ON s.id = c.source_id
            WHERE e.model = ?{category_clause}
            """,
            params,
        ).fetchall()
    semantic: list[dict[str, Any]] = []
    for row in rows:
        vector = [float(value) for value in json.loads(row["vector_json"])]
        score = _cosine(query_vector, vector)
        item = _row_to_chunk(row, score=score)
        item["semantic_score"] = score
        semantic.append(item)
    semantic.sort(key=lambda item: item["semantic_score"] or 0.0, reverse=True)
    merged: dict[str, dict[str, Any]] = {item["id"]: item for item in lexical}
    for item in semantic[: max(request.limit * 3, 30)]:
        existing = merged.get(item["id"])
        if existing:
            existing["semantic_score"] = item["semantic_score"]
            existing["score"] = existing["score"] + max(0.0, item["semantic_score"] or 0.0)
        else:
            merged[item["id"]] = item
    result = list(merged.values())
    result.sort(
        key=lambda item: (item["semantic_score"] or 0.0, item["score"]),
        reverse=True,
    )
    return result[: request.limit]


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Knowledge model did not return a JSON object")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise TypeError("Knowledge model returned an invalid payload")
    return payload


async def grammar_review(request: GrammarReviewRequest) -> dict[str, Any]:
    query = (
        "grammar punctuation comma semicolon colon run-on comma splice fragment subject verb "
        "pronoun agreement passive voice parallel structure"
    )
    rules = lexical_search(query, ["grammar"], 24)
    rule_text = "\n\n".join(
        f"RULE {item['id']} — {item['title']}\nAuthority: {item['authority']}\n{item['body']}"
        for item in rules
    )
    raw = await generate(
        request.provider,
        [
            {
                "role": "system",
                "content": (
                    "You are EmberWriter's grammar reviewer for fiction. Use ONLY the supplied rules as "
                    "normative grammar evidence. Distinguish grammatical error from intentional fiction style, "
                    "fragments, dialogue voice, and rhetorical punctuation. Return valid JSON only. Every issue "
                    "must cite one or more supplied rule IDs. Do not rewrite the passage wholesale."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"CONTEXT\n{request.context or '(none)'}\n\nRULES\n{rule_text}\n\n"
                    f"PASSAGE\n{request.text}\n\nReturn this shape:\n"
                    '{"summary":"...","issues":[{"quote":"exact short quote","rule_ids":["rule-id"],'
                    '"explanation":"...","suggestion":"...","confidence":0.9,'
                    '"intentional_style_possible":false}]}'
                ),
            },
        ],
        temperature=0.15,
        top_p=0.85,
        json_mode=True,
    )
    payload = _parse_json_object(raw)
    allowed = {item["id"] for item in rules}
    issues = []
    for raw_issue in payload.get("issues", []):
        if not isinstance(raw_issue, dict):
            continue
        cited = [str(item) for item in raw_issue.get("rule_ids", []) if str(item) in allowed]
        if not cited:
            continue
        try:
            issue = GrammarIssue.model_validate({**raw_issue, "rule_ids": cited})
        except ValueError:
            continue
        issues.append(issue.model_dump())
    return {
        "summary": str(payload.get("summary", "")).strip(),
        "issues": issues,
        "rules": rules,
    }


async def answer_knowledge(request: KnowledgeAnswerRequest) -> dict[str, Any]:
    rules = lexical_search(request.question, [request.category], 14)
    if not rules:
        return {"answer": "No matching trusted rule is currently indexed.", "rules": []}
    rule_text = "\n\n".join(
        f"[{item['id']}] {item['title']}\nAuthority: {item['authority']}\n{item['body']}"
        for item in rules
    )
    answer = await generate(
        request.provider,
        [
            {
                "role": "system",
                "content": (
                    "Answer using only the supplied EmberWriter knowledge-base excerpts. Cite supporting rule IDs "
                    "in square brackets. If the excerpts do not establish the answer, say that directly. "
                    "Publishing requirements can change; mention the checked source context when relevant."
                ),
            },
            {
                "role": "user",
                "content": f"QUESTION\n{request.question}\n\nTRUSTED EXCERPTS\n{rule_text}",
            },
        ],
        temperature=0.2,
        top_p=0.85,
    )
    return {"answer": answer, "rules": rules}
