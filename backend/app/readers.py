from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Any
from uuid import uuid4

from .generation import generate
from .models import ProviderConfig
from .publishing import compiled_documents
from .reader_models import ReaderRunCreate, ReaderVerdict
from .storage import project_root, read_text, utc_now

PERSONAS: dict[str, dict[str, Any]] = {
    "fan": {
        "id": "fan",
        "name": "Genre Fan",
        "description": "Reads for emotional payoff, immersion, favorite characters, tension, surprises, and whether the book delivers the pleasures promised by its genre.",
        "lens": ["emotional response", "favorite moments", "anticipation", "genre pleasure", "would recommend"],
    },
    "casual_reader": {
        "id": "casual_reader",
        "name": "Casual Reader",
        "description": "Reads like an interested but non-specialist customer who will stop when confused, bored, overloaded, or unconvinced.",
        "lens": ["clarity", "momentum", "accessibility", "character attachment", "willingness to continue"],
    },
    "strong_editor": {
        "id": "strong_editor",
        "name": "Strong Editor",
        "description": "Reads developmentally and critically, tracking structure, causality, stakes, pacing, POV, promises/payoffs, continuity, and voice without flattening author style.",
        "lens": ["structure", "causality", "stakes", "pacing", "character arc", "continuity", "voice"],
    },
}

CHAPTER_SCHEMA = """{
  "reaction": "reader reaction in this persona's voice",
  "engagement": 1,
  "pacing": 1,
  "clarity": 1,
  "emotional_impact": 1,
  "favorite_moment": "",
  "confusion": [""],
  "predictions": [""],
  "character_reactions": [""],
  "keep_reading": "",
  "craft_notes": [""]
}"""

VERDICT_SCHEMA = """{
  "overall_reaction": "",
  "score": 1,
  "audience_fit": "",
  "genre_fit": "",
  "strongest_elements": [""],
  "weakest_elements": [""],
  "character_feedback": [""],
  "pacing_feedback": [""],
  "plot_feedback": [""],
  "voice_feedback": [""],
  "ending_feedback": [""],
  "unresolved_confusion": [""],
  "fulfilled_predictions": [""],
  "broken_promises": [""],
  "top_revisions": [""],
  "would_recommend": ""
}"""


def persona_catalog() -> list[dict[str, Any]]:
    return [dict(value) for value in PERSONAS.values()]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_json_object(text: str, label: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"{label} model did not return a JSON object")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} model returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"{label} model returned an invalid payload")
    return payload


def _connect(slug: str) -> sqlite3.Connection:
    path = project_root(slug) / ".ember" / "story.db"
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS reader_runs (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            persona TEXT NOT NULL,
            genre TEXT NOT NULL,
            focus TEXT NOT NULL,
            status TEXT NOT NULL,
            current_index INTEGER NOT NULL,
            total_documents INTEGER NOT NULL,
            document_manifest_json TEXT NOT NULL,
            verdict_json TEXT
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS reader_notes (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            path TEXT NOT NULL,
            binder_node_id TEXT,
            position INTEGER NOT NULL,
            chapter_title TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(run_id, position)
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_reader_notes_run ON reader_notes(run_id, position)")
    con.commit()
    return con


def create_reader_run(slug: str, request: ReaderRunCreate) -> dict[str, Any]:
    if request.persona not in PERSONAS:
        raise ValueError("Unknown reader persona")
    documents = compiled_documents(slug)
    manifest = [
        {
            "path": document["path"],
            "binder_node_id": document["id"],
            "title": document["title"],
            "position": index,
        }
        for index, document in enumerate(documents)
    ]
    now = utc_now()
    run_id = uuid4().hex
    with _connect(slug) as con:
        con.execute(
            """
            INSERT INTO reader_runs
            (id, created_at, updated_at, persona, genre, focus, status, current_index,
             total_documents, document_manifest_json, verdict_json)
            VALUES (?, ?, ?, ?, ?, ?, 'reading', 0, ?, ?, NULL)
            """,
            (
                run_id,
                now,
                now,
                request.persona,
                request.genre.strip(),
                request.focus.strip(),
                len(manifest),
                json.dumps(manifest),
            ),
        )
    return get_reader_run(slug, run_id)


def _note_from_row(slug: str, row: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(row["response_json"])
    try:
        stale = _hash(read_text(slug, row["path"])) != row["source_hash"]
    except (FileNotFoundError, OSError, UnicodeError, ValueError):
        stale = True
    return {
        "id": row["id"],
        "path": row["path"],
        "binder_node_id": row["binder_node_id"],
        "position": row["position"],
        "chapter_title": row["chapter_title"],
        **payload,
        "source_hash": row["source_hash"],
        "stale": stale,
    }


def _run_base(row: sqlite3.Row) -> dict[str, Any]:
    persona = PERSONAS.get(row["persona"], {"name": row["persona"]})
    verdict = json.loads(row["verdict_json"]) if row["verdict_json"] else None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "persona": row["persona"],
        "persona_name": persona["name"],
        "genre": row["genre"],
        "focus": row["focus"],
        "status": row["status"],
        "current_index": row["current_index"],
        "total_documents": row["total_documents"],
        "verdict": verdict,
    }


def get_reader_run(slug: str, run_id: str) -> dict[str, Any]:
    with _connect(slug) as con:
        row = con.execute("SELECT * FROM reader_runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(run_id)
        note_rows = con.execute(
            "SELECT * FROM reader_notes WHERE run_id = ? ORDER BY position",
            (run_id,),
        ).fetchall()
    notes = [_note_from_row(slug, note) for note in note_rows]
    return {**_run_base(row), "notes": notes, "stale_documents": sum(note["stale"] for note in notes)}


def list_reader_runs(slug: str, limit: int = 30) -> list[dict[str, Any]]:
    with _connect(slug) as con:
        rows = con.execute(
            "SELECT * FROM reader_runs ORDER BY updated_at DESC LIMIT ?",
            (max(1, min(limit, 100)),),
        ).fetchall()
    result = []
    for row in rows:
        run = get_reader_run(slug, row["id"])
        result.append(
            {
                **{key: run[key] for key in (
                    "id", "created_at", "updated_at", "persona", "persona_name", "genre", "focus",
                    "status", "current_index", "total_documents", "stale_documents"
                )},
                "score": run["verdict"]["score"] if run["verdict"] else None,
                "metadata": {},
            }
        )
    return result


def _prior_reader_context(notes: list[dict[str, Any]]) -> str:
    if not notes:
        return "This is the first document. You have no prior knowledge beyond what the book has shown here."
    recent = notes[-4:]
    chunks = []
    for note in recent:
        chunks.append(
            f"{note['chapter_title']}: reaction={note['reaction']}\n"
            f"confusion={json.dumps(note['confusion'])}\n"
            f"predictions={json.dumps(note['predictions'])}\n"
            f"character_reactions={json.dumps(note['character_reactions'])}"
        )
    return "\n\n".join(chunks)


async def _read_next_chapter(slug: str, row: sqlite3.Row, provider: ProviderConfig) -> dict[str, Any]:
    manifest = json.loads(row["document_manifest_json"])
    position = row["current_index"]
    if position >= len(manifest):
        raise ValueError("All documents have already been read")
    document = manifest[position]
    source = read_text(slug, document["path"])
    persona = PERSONAS[row["persona"]]
    existing = get_reader_run(slug, row["id"])
    prior_context = _prior_reader_context(existing["notes"])
    focus = row["focus"] or "No special focus; react naturally through the assigned reader lens."
    system = f"""You are EmberWriter's {persona['name']} simulated reader for {row['genre']} fiction.
You are reading the manuscript in order. React only to information available up to this point; do not invent later-book knowledge.
Your lens: {', '.join(persona['lens'])}.
Be specific and candid. Preserve the difference between personal taste and an actual clarity/structure problem.
For fiction with mature adult content, evaluate whether intimacy serves character, tension, voice, plot, and emotional payoff rather than objecting merely because it is explicit.
Return ONLY valid JSON matching this schema, with all scores as integers from 1 to 10:
{CHAPTER_SCHEMA}
"""
    user = f"""GENRE
{row['genre']}

AUTHOR FOCUS
{focus}

YOUR READING MEMORY FROM EARLIER DOCUMENTS
{prior_context}

CURRENT DOCUMENT: {document['title']}
PATH: {document['path']}

{source}
"""
    raw = await generate(
        provider,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.65,
        top_p=0.9,
        json_mode=True,
    )
    payload = _parse_json_object(raw, "Reader")
    for key in ("engagement", "pacing", "clarity", "emotional_impact"):
        try:
            payload[key] = min(10, max(1, int(payload.get(key, 5))))
        except (TypeError, ValueError):
            payload[key] = 5
    for key in ("confusion", "predictions", "character_reactions", "craft_notes"):
        value = payload.get(key, [])
        payload[key] = [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []
    for key in ("reaction", "favorite_moment", "keep_reading"):
        payload[key] = str(payload.get(key, "")).strip()
    note_id = uuid4().hex
    now = utc_now()
    digest = _hash(source)
    next_index = position + 1
    next_status = "ready_to_synthesize" if next_index >= len(manifest) else "reading"
    with _connect(slug) as con:
        con.execute(
            """
            INSERT OR REPLACE INTO reader_notes
            (id, run_id, path, binder_node_id, position, chapter_title, source_hash, response_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                row["id"],
                document["path"],
                document.get("binder_node_id"),
                position,
                document["title"],
                digest,
                json.dumps(payload, ensure_ascii=False),
                now,
            ),
        )
        con.execute(
            "UPDATE reader_runs SET current_index = ?, status = ?, updated_at = ? WHERE id = ?",
            (next_index, next_status, now, row["id"]),
        )
    run = get_reader_run(slug, row["id"])
    note = next(item for item in run["notes"] if item["id"] == note_id)
    return {"run": run, "action": "chapter_read", "chapter_note": note}


async def _synthesize(slug: str, row: sqlite3.Row, provider: ProviderConfig) -> dict[str, Any]:
    run = get_reader_run(slug, row["id"])
    if not run["notes"] or len(run["notes"]) < row["total_documents"]:
        raise ValueError("Reader has not finished the manuscript")
    persona = PERSONAS[row["persona"]]
    condensed = []
    for note in run["notes"]:
        condensed.append(
            {
                "chapter": note["chapter_title"],
                "reaction": note["reaction"],
                "engagement": note["engagement"],
                "pacing": note["pacing"],
                "clarity": note["clarity"],
                "emotional_impact": note["emotional_impact"],
                "favorite_moment": note["favorite_moment"],
                "confusion": note["confusion"],
                "predictions": note["predictions"],
                "character_reactions": note["character_reactions"],
                "craft_notes": note["craft_notes"],
            }
        )
    system = f"""You are EmberWriter's {persona['name']} simulated reader finishing a {row['genre']} manuscript.
Synthesize your chapter-by-chapter reading experience. Do not pretend to be statistically representative of all readers. Distinguish taste from defects.
Track whether early predictions/questions paid off, whether promises were fulfilled, where momentum rose/fell, and whether the ending satisfied this genre-reader lens.
For mature adult fiction, judge explicit material by craft, characterization, tension, consent/continuity, emotional consequence, and genre fit—not by mere explicitness.
Return ONLY valid JSON matching:
{VERDICT_SCHEMA}
"""
    user = f"""AUTHOR FOCUS
{row['focus'] or 'No special focus.'}

CHAPTER-BY-CHAPTER READER NOTES
{json.dumps(condensed, ensure_ascii=False)}
"""
    raw = await generate(
        provider,
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.55,
        top_p=0.9,
        json_mode=True,
    )
    payload = _parse_json_object(raw, "Reader verdict")
    try:
        payload["score"] = min(10, max(1, int(payload.get("score", 5))))
    except (TypeError, ValueError):
        payload["score"] = 5
    for key in (
        "strongest_elements", "weakest_elements", "character_feedback", "pacing_feedback",
        "plot_feedback", "voice_feedback", "ending_feedback", "unresolved_confusion",
        "fulfilled_predictions", "broken_promises", "top_revisions",
    ):
        value = payload.get(key, [])
        payload[key] = [str(item).strip() for item in value if str(item).strip()] if isinstance(value, list) else []
    for key in ("overall_reaction", "audience_fit", "genre_fit", "would_recommend"):
        payload[key] = str(payload.get(key, "")).strip()
    verdict = ReaderVerdict.model_validate(payload).model_dump()
    now = utc_now()
    with _connect(slug) as con:
        con.execute(
            "UPDATE reader_runs SET verdict_json = ?, status = 'completed', updated_at = ? WHERE id = ?",
            (json.dumps(verdict, ensure_ascii=False), now, row["id"]),
        )
    return {"run": get_reader_run(slug, row["id"]), "action": "synthesized", "chapter_note": None}


async def step_reader_run(slug: str, run_id: str, provider: ProviderConfig) -> dict[str, Any]:
    with _connect(slug) as con:
        row = con.execute("SELECT * FROM reader_runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise FileNotFoundError(run_id)
    if row["status"] == "completed":
        raise ValueError("Reader run is already complete")
    if row["status"] == "ready_to_synthesize":
        return await _synthesize(slug, row, provider)
    return await _read_next_chapter(slug, row, provider)
