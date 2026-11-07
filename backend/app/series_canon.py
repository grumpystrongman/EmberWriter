"""Source-anchored, author-approved canon graph and spoiler-scoped temporal queries.

AI (or any integration) may propose but cannot approve facts. Temporal state
keeps world truth, characters' beliefs, and reader reveals separate. Every
approved claim is tied to an immutable author-authorized source snapshot.
"""
from __future__ import annotations

import json
import re
import sqlite3

from .series_vault import _connect, _id, _one, now, source_text

KINDS = {"character", "place", "artifact", "faction", "species", "rule", "event", "concept"}
SCOPES = {"world", "character_belief", "reader_reveal"}
STATUS = {"proposed", "approved", "rejected"}
WORD = re.compile(r"[\w'-]+", re.UNICODE)
STOP = {"the", "and", "about", "what", "which", "where", "when", "did", "does",
        "have", "has", "was", "were", "that", "this", "with", "from", "book",
        "tell", "know", "knew", "why", "how", "who", "their", "there", "are"}


def _entity(con: sqlite3.Connection, series_id: str, identifier: str) -> dict:
    return _one(con, "SELECT * FROM entities WHERE id=? AND series_id=?",
                (identifier, series_id))


def list_entities(series_id: str) -> list[dict]:
    with _connect() as con:
        _one(con, "SELECT id FROM series WHERE id=?", (series_id,))
        items = [dict(r) for r in con.execute(
            "SELECT * FROM entities WHERE series_id=? ORDER BY name COLLATE NOCASE",
            (series_id,))]
    for item in items:
        item["aliases"] = json.loads(item["aliases"])
    return items


def add_entity(series_id: str, name: str, kind: str, *,
               aliases: list[str] | None = None, description: str = "") -> dict:
    name = name.strip()
    aliases = aliases or []
    if not 1 <= len(name) <= 120 or kind not in KINDS or len(description) > 3000:
        raise ValueError("Entity name, type or description is invalid")
    if len(aliases) > 30 or any(not 1 <= len(a.strip()) <= 120 for a in aliases):
        raise ValueError("Aliases must be a list of up to 30 short names")
    cleaned = sorted({a.strip() for a in aliases if a.strip().casefold() != name.casefold()})
    if any(name.casefold() == item["name"].casefold()
           for item in list_entities(series_id)):
        raise ValueError("An entity with that name already exists")
    identifier = _id()
    with _connect() as con:
        _one(con, "SELECT id FROM series WHERE id=?", (series_id,))
        con.execute("INSERT INTO entities VALUES (?,?,?,?,?,?,?)",
                    (identifier, series_id, name, kind, json.dumps(cleaned),
                     description.strip(), now()))
    return next(item for item in list_entities(series_id) if item["id"] == identifier)


def edit_entity(series_id: str, entity_id: str, *,
                aliases: list[str], description: str) -> dict:
    if len(aliases) > 30 or any(not 1 <= len(a.strip()) <= 120 for a in aliases):
        raise ValueError("Aliases must be at most 30 short names")
    if len(description) > 3000:
        raise ValueError("Entity description exceeds 3,000 characters")
    with _connect() as con:
        entity = _entity(con, series_id, entity_id)
        con.execute("UPDATE entities SET aliases=?, description=? WHERE id=?",
                    (json.dumps(sorted({a.strip() for a in aliases
                                        if a.strip().casefold() != entity["name"].casefold()})),
                     description.strip(), entity_id))
    return next(item for item in list_entities(series_id) if item["id"] == entity_id)


def _time(book: int, sequence: int) -> tuple[int, int]:
    if not 1 <= book <= 9999 or not 0 <= sequence <= 999999:
        raise ValueError("Timeline book and scene sequence are out of range")
    return book, sequence


def _validate_source(series_id: str, source_id: str, begin: int, end: int,
                     quote: str) -> tuple[dict, str]:
    item, text = source_text(series_id, source_id)
    if not (0 <= begin < end <= len(text)):
        raise ValueError("Evidence character offsets do not match the source")
    if not quote or len(quote) > 2000:
        raise ValueError("Quote must be 1–2,000 characters")
    if text[begin:end] != quote:
        raise ValueError("The quoted source text differs from its immutable snapshot")
    return item, text


def propose_fact(series_id: str, subject_id: str, predicate: str, *,
                 object_text: str = "", object_entity_id: str | None = None,
                 scope: str = "world", knower_id: str | None = None,
                 start_book: int, start_sequence: int = 0,
                 end_book: int | None = None, end_sequence: int | None = None,
                 source_id: str, quote_start: int, quote_end: int, quote: str,
                 note: str = "") -> dict:
    predicate = predicate.strip().lower().replace(" ", "_")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,59}", predicate):
        raise ValueError("Predicate must be a short snake_case relationship")
    if (not object_text.strip() and not object_entity_id) or len(object_text) > 500:
        raise ValueError("Give this fact a target entity or a short value")
    if scope not in SCOPES:
        raise ValueError("Fact scope must be world, character_belief or reader_reveal")
    if scope == "character_belief" and not knower_id:
        raise ValueError("A character belief must specify who believes it")
    if scope != "character_belief" and knower_id:
        raise ValueError("Only a character belief can identify a knowledge holder")
    if len(note) > 1200:
        raise ValueError("Fact note exceeds 1,200 characters")
    begin = _time(start_book, start_sequence)
    end = _time(end_book, end_sequence if end_sequence is not None else 999999) if end_book else None
    if end and end < begin:
        raise ValueError("A fact cannot end before it begins")
    source, _ = _validate_source(series_id, source_id, quote_start, quote_end, quote)
    if start_book < source["ordinal"]:
        raise ValueError("Do not place a source-grounded fact before the book that establishes it")
    with _connect() as con:
        _entity(con, series_id, subject_id)
        if object_entity_id:
            _entity(con, series_id, object_entity_id)
        if knower_id:
            holder = _entity(con, series_id, knower_id)
            if holder["kind"] != "character":
                raise ValueError("Only a character can hold a belief")
        if not con.execute(
            "SELECT 1 FROM volumes WHERE series_id=? AND ordinal=?", (series_id, start_book)
        ).fetchone():
            raise ValueError("Start book must exist in the Series Vault")
        if end_book and not con.execute(
            "SELECT 1 FROM volumes WHERE series_id=? AND ordinal=?", (series_id, end_book)
        ).fetchone():
            raise ValueError("End book must exist in the Series Vault")
        identifier = _id()
        con.execute("""
            INSERT INTO assertions (
                id,series_id,subject_id,predicate,object_text,object_entity_id,
                scope,knower_id,start_book,start_sequence,end_book,end_sequence,
                source_id,quote_start,quote_end,quote,status,note,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (identifier, series_id, subject_id, predicate, object_text.strip(),
              object_entity_id, scope, knower_id, start_book, start_sequence,
              end_book, end[1] if end else None, source_id,
              quote_start, quote_end, quote, "proposed", note.strip(), now()))
    return fact(series_id, identifier)


def _facts_sql() -> str:
    return """
        SELECT assertions.*, e.name AS subject_name, e.kind AS subject_kind,
               obj.name AS object_name, knower.name AS knower_name,
               src.title AS source_title, src.source_path, src.sha256 AS source_sha256,
               v.title AS source_volume_title, v.ordinal AS source_book,
               v.kind AS source_volume_kind, v.edition_status AS source_edition_status
        FROM assertions
        JOIN entities e ON e.id=assertions.subject_id
        LEFT JOIN entities obj ON obj.id=assertions.object_entity_id
        LEFT JOIN entities knower ON knower.id=assertions.knower_id
        JOIN sources src ON src.id=assertions.source_id
        JOIN volumes v ON v.id=src.volume_id
    """


def _read_facts(con: sqlite3.Connection, where: str, params: tuple) -> list[dict]:
    rows = [dict(r) for r in con.execute(
        _facts_sql() + " WHERE " + where +
        " ORDER BY assertions.start_book, assertions.start_sequence, assertions.created_at",
        params)]
    for row in rows:
        row["reference"] = {
            "source_id": row["source_id"],
            "source_path": row["source_path"],
            "title": row["source_title"], "volume": row["source_volume_title"],
            "book": row["source_book"], "sha256": row["source_sha256"],
            "quote": row["quote"], "start": row["quote_start"], "end": row["quote_end"],
        }
    return rows


def fact(series_id: str, fact_id: str) -> dict:
    with _connect() as con:
        items = _read_facts(con, "assertions.id=? AND assertions.series_id=?",
                            (fact_id, series_id))
    if not items:
        raise FileNotFoundError("Canon assertion not found")
    return items[0]


def review_fact(series_id: str, fact_id: str, decision: str) -> dict:
    if decision not in {"approved", "rejected"}:
        raise ValueError("Choose approve or reject")
    with _connect() as con:
        existing = _read_facts(con, "assertions.id=? AND assertions.series_id=?",
                               (fact_id, series_id))
        if not existing:
            raise FileNotFoundError("Canon assertion not found")
        if existing[0]["status"] != "proposed":
            raise ValueError("Reviewed canon is immutable; propose a sourced successor")
        source = existing[0]
        _validate_source(series_id, source["source_id"], source["quote_start"],
                         source["quote_end"], source["quote"])
        con.execute("UPDATE assertions SET status=? WHERE id=?", (decision, fact_id))
    return fact(series_id, fact_id)


def list_facts(series_id: str, *, status: str | None = None,
               subject_id: str | None = None) -> list[dict]:
    if status and status not in STATUS:
        raise ValueError("Unknown review status")
    terms = ["assertions.series_id=?"]
    args: list[str] = [series_id]
    if status:
        terms.append("assertions.status=?")
        args.append(status)
    if subject_id:
        terms.append("assertions.subject_id=?")
        args.append(subject_id)
    with _connect() as con:
        _one(con, "SELECT id FROM series WHERE id=?", (series_id,))
        return _read_facts(con, " AND ".join(terms), tuple(args))


def at_book(series_id: str, book: int, sequence: int = 999999, *,
            scope: str = "world", subject_id: str | None = None,
            knower_id: str | None = None) -> dict:
    point = _time(book, sequence)
    if scope not in SCOPES:
        raise ValueError("Unknown knowledge scope")
    if scope == "character_belief" and not knower_id:
        raise ValueError("Select the character whose knowledge you want to inspect")
    with _connect() as con:
        volume = _one(con, "SELECT * FROM volumes WHERE series_id=? AND ordinal=?",
                      (series_id, book))
        terms = [
            "assertions.series_id=?", "assertions.status='approved'",
            "assertions.scope=?", "v.ordinal<=?",
            "(assertions.start_book < ? OR (assertions.start_book=? AND assertions.start_sequence<=?))",
            "(assertions.end_book IS NULL OR assertions.end_book > ? OR (assertions.end_book=? AND assertions.end_sequence>=?))",
        ]
        args: list[str | int] = [series_id, scope, book, book, book, sequence,
                                 book, book, sequence]
        if subject_id:
            _entity(con, series_id, subject_id)
            terms.append("assertions.subject_id=?")
            args.append(subject_id)
        if knower_id:
            _entity(con, series_id, knower_id)
            terms.append("assertions.knower_id=?")
            args.append(knower_id)
        records = _read_facts(con, " AND ".join(terms), tuple(args))
    conflicts: list[dict] = []
    groups: dict[tuple[str, str, str, str], list[dict]] = {}
    for claim in records:
        key = (claim["subject_id"], claim["predicate"], claim["scope"],
               claim["knower_id"] or "")
        groups.setdefault(key, []).append(claim)
    for group in groups.values():
        values = {(row["object_entity_id"], row["object_text"]) for row in group}
        if len(group) > 1 and len(values) > 1:
            conflicts.append({
                "subject": group[0]["subject_name"], "predicate": group[0]["predicate"],
                "assertion_ids": [row["id"] for row in group],
                "note": "Competing approved assertions; author review required",
            })
    return {"series_id": series_id, "book": volume, "sequence": point[1],
            "scope": scope, "knower_id": knower_id,
            "facts": records, "conflicts": conflicts, "spoiler_limit": book}


def timeline(series_id: str, *, subject_id: str | None = None) -> dict:
    with _connect() as con:
        _one(con, "SELECT id FROM series WHERE id=?", (series_id,))
        where = "assertions.series_id=? AND assertions.status='approved'"
        args: tuple = (series_id,)
        if subject_id:
            _entity(con, series_id, subject_id)
            where += " AND assertions.subject_id=?"
            args += (subject_id,)
        records = _read_facts(con, where, args)
    return {"series_id": series_id, "events": records}


def ask_temporal(series_id: str, question: str, book: int, *,
                 sequence: int = 999999, scope: str = "world",
                 knower_id: str | None = None) -> dict:
    """Deterministic evidence-first answers: no generated claim or citation."""
    if not 3 <= len(question.strip()) <= 1500:
        raise ValueError("Ask a question between 3 and 1,500 characters")
    entities = list_entities(series_id)
    lower = question.casefold()
    mentions = []
    for entity in entities:
        names = [entity["name"], *entity["aliases"]]
        for name in names:
            if re.search(r"(?<!\w)" + re.escape(name.casefold()) + r"(?!\w)", lower):
                mentions.append((len(name), entity))
                break
    mentions.sort(key=lambda row: -row[0])
    subject_id = mentions[0][1]["id"] if mentions else None
    if scope == "character_belief" and knower_id:
        mentions = [row for row in mentions if row[1]["id"] != knower_id]
        subject_id = mentions[0][1]["id"] if mentions else None
    state = at_book(series_id, book, sequence, scope=scope,
                    subject_id=subject_id, knower_id=knower_id)
    tokens = set(WORD.findall(lower)) - STOP
    ranked = []
    for claim in state["facts"]:
        haystack = set(WORD.findall(
            (claim["predicate"].replace("_", " ") + " " + claim["object_text"] +
             " " + claim["subject_name"]).casefold()))
        score = len(tokens & haystack)
        if subject_id and claim["subject_id"] == subject_id:
            score += 4
        ranked.append((score, claim))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]["start_book"],
                                  pair[1]["start_sequence"]))
    selected = [row for _, row in ranked[:12]]
    if not selected:
        answer = ("I can't establish an answer from approved, source-linked facts "
                  f"available by Book {book} in the selected knowledge scope.")
    else:
        lines = []
        for index, row in enumerate(selected, 1):
            value = row["object_name"] or row["object_text"]
            prefix = (row["knower_name"] + " believes " if scope == "character_belief"
                      else "Readers learn " if scope == "reader_reveal" else "")
            lines.append(
                f"[{index}] {prefix}{row['subject_name']} — "
                f"{row['predicate'].replace('_', ' ')} — {value} "
                f"(Book {row['source_book']}, {row['source_title']}).")
        answer = "Here are the relevant approved facts with their sources:\n" + "\n".join(lines)
        if state["conflicts"]:
            answer += "\nPossible conflicts exist among these approved claims; see below."
    return {"answer": answer, "question": question,
            "matched_entity_id": subject_id,
            "sources": [row["reference"] for row in selected],
            "facts": selected, "conflicts": state["conflicts"],
            "scope": scope, "book": book, "sequence": sequence,
            "evidence_only": True, "read_only": True}
