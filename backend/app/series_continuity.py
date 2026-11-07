"""Non-destructive, evidence-based continuity checks for a proposed scene.

No model guess is treated as a contradiction. The guardian compares an
author-supplied structured scene assertion to reviewed, time-scoped canon.
Text scanning supplies *possible* entity mentions, never asserted facts.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from .series_canon import at_book, list_entities, list_facts
from .series_vault import _connect, _id, _one, now, series_detail, source_text

MAX_SCENE = 35_000
REASONS = {"intentional_retcon", "unreliable_narrator", "false_belief",
           "intentional_misdirection", "draft_in_progress", "other"}
TOKENS = re.compile(r"(?<!\w){}(?!\w)", re.IGNORECASE)


def _setup() -> None:
    with _connect() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS continuity_exceptions (
                id TEXT PRIMARY KEY,
                series_id TEXT NOT NULL REFERENCES series(id),
                claim_key TEXT NOT NULL, reason TEXT NOT NULL,
                note TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(series_id, claim_key)
            );
            CREATE INDEX IF NOT EXISTS continuity_exceptions_series
              ON continuity_exceptions(series_id);
        """)


def _claim_key(series_id: str, book: int, subject_id: str, predicate: str,
               object_value: str, scope: str, knower_id: str | None,
               scene_hash: str) -> str:
    raw = json.dumps([series_id, book, subject_id, predicate,
                      object_value.strip().casefold(), scope, knower_id, scene_hash],
                     separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _patterns(entity: dict) -> list[re.Pattern]:
    return [re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)", re.IGNORECASE)
            for name in [entity["name"], *entity["aliases"]] if len(name) >= 2]


def _mention_ranges(scene: str, entity: dict) -> list[dict]:
    ranges = []
    seen: set[tuple[int, int]] = set()
    for expression in _patterns(entity):
        for match in expression.finditer(scene):
            key = match.span()
            if key in seen:
                continue
            seen.add(key)
            a = max(0, match.start() - 160)
            b = min(len(scene), match.end() + 160)
            ranges.append({"start": match.start(), "end": match.end(),
                           "excerpt": scene[a:b], "excerpt_start": a})
            if len(ranges) >= 15:
                return sorted(ranges, key=lambda x: x["start"])
    return sorted(ranges, key=lambda x: x["start"])


def list_exceptions(series_id: str) -> list[dict]:
    _setup()
    with _connect() as con:
        _one(con, "SELECT id FROM series WHERE id=?", (series_id,))
        return [dict(row) for row in con.execute(
            "SELECT * FROM continuity_exceptions WHERE series_id=? ORDER BY created_at",
            (series_id,))]


def annotate_exception(series_id: str, claim_key: str, reason: str, note: str) -> dict:
    _setup()
    if not re.fullmatch(r"[a-f0-9]{64}", claim_key):
        raise ValueError("Invalid finding identifier")
    if reason not in REASONS or not 1 <= len(note.strip()) <= 1000:
        raise ValueError("Choose a reason and write a short author explanation")
    # Only an existing, server-computed finding from a stored scan is eligible
    # for an intentional-exception override.
    with _connect() as con:
        _one(con, "SELECT id FROM series WHERE id=?", (series_id,))
        row = con.execute(
            "SELECT id,claim_key FROM continuity_findings "
            "WHERE series_id=? AND claim_key=?",
            (series_id, claim_key),
        ).fetchone()
        if not row:
            raise ValueError("Run a source-grounded check before saving an exception")
        identifier = _id()
        con.execute("""
            INSERT INTO continuity_exceptions(id,series_id,claim_key,reason,note,created_at)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(series_id,claim_key) DO UPDATE SET
                reason=excluded.reason,note=excluded.note,created_at=excluded.created_at
            """, (identifier, series_id, claim_key, reason, note.strip(), now()))
    return next(x for x in list_exceptions(series_id) if x["claim_key"] == claim_key)


def clear_exception(series_id: str, claim_key: str) -> dict:
    _setup()
    with _connect() as con:
        result = con.execute(
            "DELETE FROM continuity_exceptions WHERE series_id=? AND claim_key=?",
            (series_id, claim_key))
    return {"cleared": bool(result.rowcount), "claim_key": claim_key}


def _scan_setup() -> None:
    _setup()
    with _connect() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS continuity_findings (
                id TEXT PRIMARY KEY, series_id TEXT NOT NULL REFERENCES series(id),
                claim_key TEXT NOT NULL,
                created_at TEXT NOT NULL, UNIQUE(series_id, claim_key)
            );
        """)


def scan_scene(series_id: str, *, scene: str, book: int, sequence: int = 999999,
               assertions: list[dict] | None = None) -> dict:
    """Check author-declared scene assertions against approved facts.

    Assertions contain subject_id, predicate, object_text OR object_entity_id,
    scope, optional knower_id. A scene passage alone only yields mentions.
    Explicit claims must come from the author, not an unchecked language model.
    """
    if not 1 <= len(scene) <= MAX_SCENE:
        raise ValueError("Scene must contain 1–35,000 characters")
    if not 1 <= book <= 9999 or not 0 <= sequence <= 999999:
        raise ValueError("Invalid target book or scene position")
    assertions = assertions or []
    if len(assertions) > 100:
        raise ValueError("Check at most 100 declared scene claims at once")
    series = series_detail(series_id)
    if book not in {item["ordinal"] for item in series["volumes"]}:
        raise ValueError("Target book must exist in the vault")
    entities = list_entities(series_id)
    index = {item["id"]: item for item in entities}
    mentions = [
        {"entity_id": entity["id"], "name": entity["name"], "kind": entity["kind"],
         "locations": _mention_ranges(scene, entity)}
        for entity in entities
    ]
    mentions = [item for item in mentions if item["locations"]]
    mentions.sort(key=lambda item: item["locations"][0]["start"])
    fingerprint = hashlib.sha256(scene.encode()).hexdigest()
    findings: list[dict] = []
    evidences: list[dict] = []
    for claim in assertions:
        subject_id = str(claim.get("subject_id", ""))
        if subject_id not in index:
            raise ValueError("A scene claim refers to an entity outside this series")
        predicate = str(claim.get("predicate", "")).strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,59}", predicate):
            raise ValueError("Scene claim predicate must be snake_case")
        value = str(claim.get("object_text") or "").strip()
        target_id = claim.get("object_entity_id")
        if target_id is not None and target_id not in index:
            raise ValueError("Scene claim target does not exist in this series")
        if not value and not target_id:
            raise ValueError("Scene claim needs a target value or entity")
        if len(value) > 500:
            raise ValueError("Claim target value is too long")
        scope = str(claim.get("scope", "world"))
        if scope not in {"world", "reader_reveal", "character_belief"}:
            raise ValueError("Unknown scene knowledge scope")
        knower = claim.get("knower_id")
        if scope == "character_belief":
            if knower not in index or index[knower]["kind"] != "character":
                raise ValueError("A belief requires an existing character")
        elif knower:
            raise ValueError("Only character beliefs can have a knower")
        point = at_book(series_id, book, sequence, scope=scope,
                        subject_id=subject_id, knower_id=knower)
        relevant = [row for row in point["facts"] if row["predicate"] == predicate]
        if not relevant:
            evidences.append({
                "subject_name": index[subject_id]["name"],
                "predicate": predicate,
                "status": "unverified", "reason": "No approved rule at the selected story point",
                "source_count": 0, "review_required": False,
            })
            continue
        intended = (target_id, value.casefold())
        agrees = [row for row in relevant if (
            row["object_entity_id"], row["object_text"].casefold()) == intended]
        if agrees:
            evidences.append({
                "subject_name": index[subject_id]["name"], "predicate": predicate,
                "status": "supported", "references": [r["reference"] for r in agrees],
                "review_required": False,
            })
            continue
        key = _claim_key(series_id, book, subject_id, predicate, value or str(target_id),
                         scope, knower, fingerprint)
        findings.append({
            "claim_key": key,
            "level": "possible_conflict",
            "subject_id": subject_id, "subject_name": index[subject_id]["name"],
            "predicate": predicate, "proposed_value": value or index[target_id]["name"],
            "scope": scope, "knower_id": knower,
            "evidence": [r["reference"] for r in relevant[:8]],
            "existing_values": [r["object_name"] or r["object_text"] for r in relevant[:8]],
            "reason": "The author-declared scene claim differs from approved canon at this point",
            "requires_author_decision": True,
        })
    _scan_setup()
    with _connect() as con:
        for finding in findings:
            con.execute(
                "INSERT OR IGNORE INTO continuity_findings VALUES (?,?,?,?)",
                (_id(), series_id, finding["claim_key"], now()))
        exceptions = {r["claim_key"]: dict(r) for r in con.execute(
            "SELECT * FROM continuity_exceptions WHERE series_id=?", (series_id,))}
    for finding in findings:
        finding["exception"] = exceptions.get(finding["claim_key"])
        finding["suppressed_by_author"] = bool(finding["exception"])
    return {
        "series_id": series_id, "book": book, "sequence": sequence,
        "scene_sha256": fingerprint, "mentions": mentions[:150],
        "findings": findings, "verified_claims": evidences,
        "limitations": "Only explicit author-declared scene claims are compared for contradictions. "
                       "Mentions are hints, not inferred events. Potential conflicts require author review.",
        "read_only": True, "manuscript_modified": False,
    }
