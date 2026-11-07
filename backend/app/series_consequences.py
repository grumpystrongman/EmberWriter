"""Consequence Engine — source-linked, non-mutating series change impact maps.

Given a hypothetical change to a known canon relationship, identifies directly
affected approved assertions, future appearances and downstream cited changes.
Broad manuscript mentions are flagged as 'inspect', not declared contradictions.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from .series_canon import list_entities, list_facts
from .series_vault import _connect, _id, _one, now, series_detail, source_text

MAX_SNIPPETS = 140
MAX_SCAN_CHARS = 24_000_000
MAX_FINDINGS = 300


def preview_change(series_id: str, *, subject_id: str, predicate: str,
                   proposed_value: str, effective_book: int,
                   scope: str = "world", include_past: bool = False) -> dict:
    series = series_detail(series_id)
    volumes = series["volumes"]
    if effective_book not in {v["ordinal"] for v in volumes}:
        raise ValueError("Effective book must exist in this series")
    entities = {r["id"]: r for r in list_entities(series_id)}
    if subject_id not in entities:
        raise ValueError("Select an entity from this series")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,59}", predicate):
        raise ValueError("Select an existing snake_case relationship")
    if not 1 <= len(proposed_value.strip()) <= 500:
        raise ValueError("Describe the proposed new value (1–500 characters)")
    if scope not in {"world", "character_belief", "reader_reveal"}:
        raise ValueError("Knowledge category is invalid")
    subject = entities[subject_id]
    names = [subject["name"], *subject["aliases"]]
    search_patterns = [
        re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", flags=re.IGNORECASE)
        for name in names if len(name) >= 2
    ]
    facts = list_facts(series_id, status="approved")
    direct: list[dict] = []
    related: list[dict] = []
    seen = set()
    for fact in facts:
        if fact["start_book"] < effective_book and not include_past:
            # Earlier source facts can still be affected by a retroactive retcon;
            # include_past is an explicit user-controlled choice.
            continue
        if fact["subject_id"] == subject_id:
            level = "direct" if fact["predicate"] == predicate and fact["scope"] == scope else "related"
        elif fact["object_entity_id"] == subject_id:
            level = "related"
        else:
            continue
        item = {
            "kind": "canon_assertion", "level": level,
            "fact_id": fact["id"], "book": fact["start_book"],
            "subject": fact["subject_name"], "predicate": fact["predicate"],
            "value": fact["object_name"] or fact["object_text"],
            "scope": fact["scope"], "reference": fact["reference"],
            "why": (
                "Same entity, relationship and knowledge scope; may contradict the proposed change"
                if level == "direct" else
                "Related approved assertion or entity relationship; review downstream implications"
            ),
        }
        if fact["id"] not in seen:
            (direct if level == "direct" else related).append(item)
            seen.add(fact["id"])
    mentions: list[dict] = []
    chars_scanned = 0
    truncated = False
    for volume in volumes:
        if volume["ordinal"] < effective_book and not include_past:
            continue
        for source in volume["sources"]:
            _, text = source_text(series_id, source["id"])
            if chars_scanned + len(text) > MAX_SCAN_CHARS:
                truncated = True
                break
            chars_scanned += len(text)
            hits = []
            for pat in search_patterns:
                for match in pat.finditer(text):
                    if match.span() not in hits:
                        hits.append(match.span())
                    if len(hits) >= 30:
                        break
            hits.sort()
            if hits:
                # One bounded preview per document; include number of occurrences
                # so the author can click through the source separately.
                a = max(0, hits[0][0] - 140)
                b = min(len(text), hits[0][1] + 230)
                mentions.append({
                    "kind": "manuscript_mention", "level": "inspect",
                    "book": volume["ordinal"],
                    "volume": volume["title"], "source_id": source["id"],
                    "source_path": source["source_path"],
                    "first_offset": hits[0][0], "hit_count": len(hits),
                    "excerpt_start": a, "excerpt": text[a:b],
                    "why": "This source mentions the affected entity; not automatically a contradiction",
                })
            if len(mentions) >= MAX_SNIPPETS:
                truncated = True
                break
        if truncated:
            break
    direct.sort(key=lambda x: (x["book"], x["fact_id"]))
    related.sort(key=lambda x: (x["book"], x["fact_id"]))
    mentions.sort(key=lambda x: (x["book"], x["source_path"]))
    # Deterministic preview hash for detecting the same proposal in future.
    signature = hashlib.sha256(
        repr((series_id, subject_id, predicate, proposed_value.strip(),
              effective_book, scope, include_past)).encode("utf-8")).hexdigest()
    return {
        "series_id": series_id, "proposal_id": signature,
        "proposal": {
            "subject_id": subject_id, "subject": subject["name"],
            "predicate": predicate, "proposed_value": proposed_value.strip(),
            "effective_book": effective_book, "scope": scope,
            "include_past": include_past,
        },
        "summary": {
            "direct_canon": len(direct), "related_canon": len(related),
            "documents_to_inspect": len(mentions), "characters_scanned": chars_scanned,
            "truncated": truncated,
        },
        "direct": direct[:MAX_FINDINGS],
        "related": related[:MAX_FINDINGS],
        "mentions": mentions,
        "read_only": True,
        "changes_applied": 0,
        "limitations": "Impact candidates are not proof of a plot error. Recheck all"
                       " cited scenes and intentional exceptions; this preview never rewrites canon.",
    }


def save_change_note(series_id: str, *, proposal_id: str, subject_id: str,
                     predicate: str, proposed_value: str, effective_book: int,
                     scope: str, include_past: bool, note: str) -> dict:
    """Author-controlled review item; deliberately NOT a canon mutation."""
    if not 1 <= len(note.strip()) <= 1500:
        raise ValueError("Explain the proposed change in 1–1,500 characters")
    preview = preview_change(
        series_id, subject_id=subject_id, predicate=predicate,
        proposed_value=proposed_value, effective_book=effective_book,
        scope=scope, include_past=include_past,
    )
    if preview["proposal_id"] != proposal_id:
        raise ValueError("Proposal changed; refresh the consequence map")
    with _connect() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS change_reviews (
                id TEXT PRIMARY KEY, series_id TEXT NOT NULL REFERENCES series(id),
                proposal_id TEXT NOT NULL, subject_id TEXT NOT NULL,
                predicate TEXT NOT NULL, proposed_value TEXT NOT NULL,
                effective_book INTEGER NOT NULL, scope TEXT NOT NULL,
                include_past INTEGER NOT NULL, author_note TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('open','dismissed')),
                created_at TEXT NOT NULL
            )
        """)
        identifier = _id()
        con.execute(
            "INSERT INTO change_reviews VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (identifier, series_id, proposal_id, subject_id, predicate,
             proposed_value.strip(), effective_book, scope, int(include_past),
             note.strip(), "open", now()),
        )
    return {"review_id": identifier, "status": "open", "canon_changed": False,
            "manuscripts_changed": False, "impact": preview["summary"]}


def change_reviews(series_id: str) -> list[dict]:
    with _connect() as con:
        _one(con, "SELECT id FROM series WHERE id=?", (series_id,))
        con.execute("""
            CREATE TABLE IF NOT EXISTS change_reviews (
                id TEXT PRIMARY KEY, series_id TEXT NOT NULL REFERENCES series(id),
                proposal_id TEXT NOT NULL, subject_id TEXT NOT NULL,
                predicate TEXT NOT NULL, proposed_value TEXT NOT NULL,
                effective_book INTEGER NOT NULL, scope TEXT NOT NULL,
                include_past INTEGER NOT NULL, author_note TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('open','dismissed')),
                created_at TEXT NOT NULL
            )
        """)
        return [dict(x) for x in con.execute(
            "SELECT * FROM change_reviews WHERE series_id=? ORDER BY created_at DESC",
            (series_id,))]


def dismiss_change(series_id: str, review_id: str) -> dict:
    with _connect() as con:
        _one(con, "SELECT id FROM series WHERE id=?", (series_id,))
        row = con.execute(
            "UPDATE change_reviews SET status='dismissed' "
            "WHERE id=? AND series_id=? AND status='open'",
            (review_id, series_id),
        )
    return {"dismissed": row.rowcount == 1, "canon_changed": False}
