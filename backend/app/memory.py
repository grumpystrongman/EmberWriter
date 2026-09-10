from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from .generation import generate
from .models import ProviderConfig
from .storage import _connect, project_root, read_text, utc_now

MEMORY_KINDS = {
    "canon",
    "character_state",
    "character_knowledge",
    "relationship",
    "timeline",
    "thread",
    "location",
    "object",
    "ability",
}

ANALYSIS_SYSTEM_PROMPT = """You are EmberWriter's narrative-memory extractor.
Analyze fiction manuscript text and return ONLY valid JSON. Extract durable story state, not prose commentary.

Rules:
- Record only facts explicitly stated or strongly established by the manuscript.
- Never invent missing names, motives, chronology, anatomy, relationships, or world rules.
- Keep character knowledge separate from objective canon: a character believing something does not make it true.
- Relationship entries should describe the current relationship change/state established in this source.
- Timeline entries should capture events that matter to chronology or continuity.
- Thread entries should capture promises, mysteries, plans, threats, unresolved questions, setup, or payoff status.
- Character-state entries should capture durable injuries, emotional commitments, goals, loyalties, location/state changes, or other facts likely to matter later.
- Prefer concise atomic facts. One relationship/fact/change per item.
- Confidence is 0.0-1.0. Importance is 1-5, where 5 is central to future continuity.

Return exactly this shape:
{
  "summary": "Concise chapter/scene memory summary",
  "facts": [
    {
      "kind": "canon|character_state|character_knowledge|relationship|timeline|thread|location|object|ability",
      "subject": "entity or event",
      "predicate": "short relationship/state verb",
      "object": "concise value or target",
      "confidence": 0.95,
      "importance": 3,
      "metadata": {"optional": "small structured details"}
    }
  ]
}
"""


def _ensure_schema(slug: str) -> None:
    with _connect(slug) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS document_analysis (
                path TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                summary TEXT NOT NULL,
                analyzed_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS narrative_facts (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                source_path TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 1.0,
                importance INTEGER NOT NULL DEFAULT 3,
                chapter_order INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_narrative_facts_source ON narrative_facts(source_path)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_narrative_facts_kind ON narrative_facts(kind)"
        )
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_narrative_facts_subject ON narrative_facts(subject)"
        )


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def chapter_order(path: str) -> int:
    name = Path(path).stem
    matches = re.findall(r"\d+", name)
    return int(matches[-1]) if matches else 0


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Memory model did not return a JSON object")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("Memory model returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise TypeError("Memory model returned an invalid payload")
    return payload


def _normalize_fact(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind", "")).strip().lower()
    subject = str(raw.get("subject", "")).strip()
    predicate = str(raw.get("predicate", "")).strip()
    obj = str(raw.get("object", "")).strip()
    if kind not in MEMORY_KINDS or not subject or not predicate or not obj:
        return None
    try:
        confidence = min(1.0, max(0.0, float(raw.get("confidence", 1.0))))
    except (TypeError, ValueError):
        confidence = 1.0
    try:
        importance = min(5, max(1, int(raw.get("importance", 3))))
    except (TypeError, ValueError):
        importance = 3
    metadata = raw.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "kind": kind,
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "confidence": confidence,
        "importance": importance,
        "metadata": metadata,
    }


def analysis_is_current(slug: str, path: str, content: str) -> bool:
    _ensure_schema(slug)
    with _connect(slug) as con:
        row = con.execute(
            "SELECT content_hash FROM document_analysis WHERE path = ?", (path,)
        ).fetchone()
    return bool(row and row["content_hash"] == content_hash(content))


def store_analysis(slug: str, path: str, content: str, payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_schema(slug)
    summary = str(payload.get("summary", "")).strip()
    facts = [fact for raw in payload.get("facts", []) if (fact := _normalize_fact(raw))]
    now = utc_now()
    order = chapter_order(path)
    digest = content_hash(content)

    with _connect(slug) as con:
        con.execute("DELETE FROM narrative_facts WHERE source_path = ?", (path,))
        for fact in facts:
            fact_id = uuid4().hex
            con.execute(
                """
                INSERT INTO narrative_facts (
                    id, kind, subject, predicate, object, source_path, confidence,
                    importance, chapter_order, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact_id,
                    fact["kind"],
                    fact["subject"],
                    fact["predicate"],
                    fact["object"],
                    path,
                    fact["confidence"],
                    fact["importance"],
                    order,
                    json.dumps(fact["metadata"], ensure_ascii=False),
                    now,
                    now,
                ),
            )
        con.execute(
            """
            INSERT INTO document_analysis(path, content_hash, summary, analyzed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                content_hash = excluded.content_hash,
                summary = excluded.summary,
                analyzed_at = excluded.analyzed_at
            """,
            (path, digest, summary, now),
        )

    export_memory(slug)
    return {"path": path, "summary": summary, "facts_written": len(facts), "skipped": False}


def list_memory(
    slug: str,
    query: str = "",
    kinds: list[str] | None = None,
    limit: int = 80,
) -> list[dict[str, Any]]:
    _ensure_schema(slug)
    with _connect(slug) as con:
        rows = con.execute(
            """
            SELECT id, kind, subject, predicate, object, source_path, confidence,
                   importance, chapter_order, metadata_json, created_at, updated_at
            FROM narrative_facts
            ORDER BY importance DESC, chapter_order DESC, updated_at DESC
            """
        ).fetchall()

    allowed = {kind for kind in (kinds or []) if kind in MEMORY_KINDS}
    terms = {term for term in re.findall(r"[a-zA-Z0-9']+", query.lower()) if len(term) > 2}
    results: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if allowed and item["kind"] not in allowed:
            continue
        haystack = " ".join(
            str(item[key]) for key in ("kind", "subject", "predicate", "object", "source_path")
        ).lower()
        matches = sum(haystack.count(term) for term in terms)
        if terms and not matches:
            continue
        item["score"] = float(item["importance"] * 2 + matches * 3 + item["confidence"])
        try:
            item["metadata"] = json.loads(item.pop("metadata_json"))
        except json.JSONDecodeError:
            item["metadata"] = {}
            item.pop("metadata_json", None)
        results.append(item)

    results.sort(key=lambda item: (item["score"], item["chapter_order"]), reverse=True)
    return results[: max(1, min(limit, 5000))]


def memory_stats(slug: str) -> dict[str, Any]:
    _ensure_schema(slug)
    with _connect(slug) as con:
        facts = con.execute("SELECT COUNT(*) AS count FROM narrative_facts").fetchone()["count"]
        documents = con.execute("SELECT COUNT(*) AS count FROM document_analysis").fetchone()["count"]
        by_kind = con.execute(
            "SELECT kind, COUNT(*) AS count FROM narrative_facts GROUP BY kind ORDER BY kind"
        ).fetchall()
    return {
        "facts": facts,
        "documents": documents,
        "by_kind": {row["kind"]: row["count"] for row in by_kind},
    }


def _recent_summaries(slug: str, limit: int = 6) -> list[dict[str, str]]:
    _ensure_schema(slug)
    with _connect(slug) as con:
        rows = [
            dict(row)
            for row in con.execute(
                "SELECT path, summary, analyzed_at FROM document_analysis WHERE summary != ''"
            ).fetchall()
        ]
    rows.sort(key=lambda row: (chapter_order(row["path"]), row["path"]), reverse=True)
    return rows[:limit]


def build_memory_context(slug: str, query: str = "", limit: int = 30) -> str:
    facts = list_memory(slug, query=query, limit=limit)
    if not facts and query:
        facts = list_memory(slug, limit=min(limit, 15))
    summaries = _recent_summaries(slug)
    if not facts and not summaries:
        return ""

    lines: list[str] = []
    if summaries:
        lines.append("## Recent analyzed story")
        for item in reversed(summaries):
            lines.append(f"- {item['path']}: {item['summary']}")
    if facts:
        if lines:
            lines.append("")
        lines.append("## Structured narrative memory")
        for fact in facts:
            lines.append(
                f"- [{fact['kind']}] {fact['subject']} — {fact['predicate']} — {fact['object']} "
                f"(source: {fact['source_path']}, confidence: {fact['confidence']:.2f})"
            )
    return "\n".join(lines)


def export_memory(slug: str) -> Path:
    _ensure_schema(slug)
    with _connect(slug) as con:
        analyses = [
            dict(row)
            for row in con.execute(
                "SELECT path, content_hash, summary, analyzed_at FROM document_analysis ORDER BY path"
            ).fetchall()
        ]
    payload = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "documents": analyses,
        "facts": list_memory(slug, limit=5000),
    }
    path = project_root(slug) / "summaries" / "narrative-memory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


async def analyze_document(
    slug: str,
    path: str,
    provider: ProviderConfig,
    force: bool = False,
) -> dict[str, Any]:
    if not path.startswith("manuscript/"):
        raise ValueError("Narrative analysis currently supports manuscript files only")
    content = read_text(slug, path)
    if not content.strip():
        raise ValueError("Cannot analyze an empty manuscript file")
    if not force and analysis_is_current(slug, path, content):
        return {"path": path, "summary": "", "facts_written": 0, "skipped": True}

    prior_memory = build_memory_context(slug, query=content[:5000], limit=20)
    user_message = f"""SOURCE PATH: {path}

PRIOR STORY MEMORY
{prior_memory or '(No prior structured memory yet.)'}

MANUSCRIPT TO ANALYZE
{content[:70000]}
"""
    raw = await generate(
        provider,
        [
            {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,
        top_p=0.9,
        json_mode=True,
    )
    return store_analysis(slug, path, content, _parse_json_object(raw))
