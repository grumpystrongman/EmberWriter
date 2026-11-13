"""Evidence-grounded, author-controlled character and continuity research.

Answers are deterministic projections of approved source quotations. This
module never infers a character's motives from name mentions, runs a model,
or promotes a proposal to canon. Chronology is authored (book + sequence),
not guessed from the EPUB offset.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import pairwise

from . import series_canon as canon
from . import series_story_state as story
from . import series_vault as vault

EXCLUSIVE_PREDICATES = canon.EXCLUSIVE_PREDICATES
CAUSAL_PREDICATES = {
    "causes", "caused_by", "leads_to", "consequence_of", "triggered_by",
    "enables", "prevents", "resolves", "pays_off", "foreshadows", "setup_for",
}
RELATIONSHIP_PREDICATES = story.RELATIONSHIPS | {
    "trust", "distrust", "friend_of", "enemy_of", "mentors",
    "mentored_by", "parent_of", "sibling_of", "confides_in",
    "resentful_of", "protective_of", "betrayed_by", "forgave",
}


def _eligible(row: dict, book: int, sequence: int) -> bool:
    return (
        row["status"] == "approved"
        and row["reference"]["book"] <= book
        and (row["start_book"], row["start_sequence"]) <= (book, sequence)
    )


def _active(row: dict, book: int, sequence: int) -> bool:
    if not _eligible(row, book, sequence):
        return False
    if row["end_book"] is None:
        return True
    return (row["end_book"], row["end_sequence"] if row["end_sequence"] is not None else 999999) >= (book, sequence)


def _sort_key(row: dict) -> tuple:
    return row["start_book"], row["start_sequence"], row["created_at"], row["id"]


def _payload(row: dict) -> dict:
    """No writable entity records or raw unbounded source documents."""
    return {
        "id": row["id"],
        "subject_id": row["subject_id"], "subject": row["subject_name"],
        "predicate": row["predicate"], "value": row["object_text"],
        "target_id": row["object_entity_id"], "target": row["object_name"],
        "scope": row["scope"], "knower_id": row["knower_id"],
        "knower": row["knower_name"],
        "from_book": row["start_book"], "from_sequence": row["start_sequence"],
        "through_book": row["end_book"], "through_sequence": row["end_sequence"],
        "citation": row["reference"],
        "status": row["status"],
    }


def investigate(series_id: str, book: int, *, sequence: int = 999999,
                subject_id: str | None = None,
                other_id: str | None = None,
                knower_id: str | None = None) -> dict:
    """Read-only evidence at a precise author-assigned story position."""
    if not 0 <= sequence <= 999999:
        raise ValueError("Scene position must be between 0 and 999999")
    detail = vault.series_detail(series_id)
    if book not in {item["ordinal"] for item in detail["volumes"]}:
        raise ValueError("Select a book in this Series Vault")
    entities = {item["id"]: item for item in canon.list_entities(series_id)}
    for selected in (subject_id, other_id, knower_id):
        if selected and selected not in entities:
            raise FileNotFoundError("Character is not present in this Series Vault")
    if knower_id and entities[knower_id]["kind"] != "character":
        raise ValueError("Only a character can hold a belief")
    # When two participants are selected, require both to occur in the
    # SAME approved assertion. A person's separate unrelated statements
    # must not masquerade as evidence of a relationship between them.
    def matches_participants(row: dict) -> bool:
        involved = {row["subject_id"], row["object_entity_id"], row["knower_id"]}
        return (not subject_id or subject_id in involved) and (
            not other_id or other_id in involved
        )

    records = sorted(
        (row for row in canon.list_facts(series_id)
         if _eligible(row, book, sequence) and matches_participants(row)),
        key=_sort_key,
    )
    active = [row for row in records if _active(row, book, sequence)]
    world = [_payload(row) for row in active if row["scope"] == "world"]
    revealed = [_payload(row) for row in active if row["scope"] == "reader_reveal"]
    beliefs = [_payload(row) for row in active if row["scope"] == "character_belief"
               and (not knower_id or row["knower_id"] == knower_id)]
    relationships = [
        _payload(row) for row in records
        if row["predicate"] in RELATIONSHIP_PREDICATES
        and row["object_entity_id"]
        and (not subject_id or row["subject_id"] == subject_id
             or row["object_entity_id"] == subject_id)
    ]
    psychology = {
        name: [_payload(row) for row in active
               if row["predicate"].lower() in predicates
               and (not subject_id or row["subject_id"] == subject_id)]
        for name, predicates in story.PSYCHOLOGY.items()
    }
    groups = defaultdict(list)
    for row in records:
        key = (row["subject_id"], row["predicate"], row["scope"], row["knower_id"] or "")
        groups[key].append(row)

    changes = []
    conflicts = []
    for group in groups.values():
        if len(group) < 2:
            continue
        for older, newer in pairwise(group):
            if (older["object_text"], older["object_entity_id"]) == (newer["object_text"], newer["object_entity_id"]):
                continue
            # Facts are not known to be mutually exclusive unless their
            # predicates denote a single-valued state. Different opinions
            # or relationships can coexist without being contradictions.
            overlap = _active(older, newer["start_book"], newer["start_sequence"])
            item = {
                "subject": older["subject_name"],
                "predicate": older["predicate"], "scope": older["scope"],
                "older": _payload(older), "newer": _payload(newer),
                "classification": (
                    "possible_conflict"
                    if overlap and older["predicate"] in EXCLUSIVE_PREDICATES
                    else ("coexisting_claims" if overlap else "recorded_change")
                ),
                "requires_author_review": True,
            }
            changes.append(item)
            if item["classification"] == "possible_conflict":
                conflicts.append(item)

    causal_links = [_payload(row) for row in records if row["predicate"] in CAUSAL_PREDICATES]
    thread_groups: dict[str, list[dict]] = defaultdict(list)
    for row in records:
        if row["predicate"] in story.THREAD_START | story.THREAD_PAYOFF | story.THREAD_SIGNAL:
            thread_groups[row["subject_id"]].append(row)
    thread_lifecycle = []
    for subject, entries in thread_groups.items():
        starts = [row for row in entries if row["predicate"] in story.THREAD_START]
        payoffs = [row for row in entries if row["predicate"] in story.THREAD_PAYOFF]
        thread_lifecycle.append({
            "subject_id": subject, "name": entries[0]["subject_name"],
            "status": "resolved" if payoffs else ("open" if starts else "unanchored"),
            "setups": [_payload(row) for row in starts],
            "payoffs": [_payload(row) for row in payoffs],
            "evidence": [_payload(row) for row in entries],
            "requires_author_review": True,
        })
    response = {
        "series_id": series_id, "as_of_book": book, "as_of_sequence": sequence,
        "subject": entities.get(subject_id), "counterpart": entities.get(other_id),
        "knower": entities.get(knower_id),
        "world_truths": world, "character_beliefs": beliefs,
        "reader_reveals": revealed, "relationships": relationships,
        "psychology": psychology, "history": [_payload(row) for row in records],
        "recorded_changes": changes, "possible_conflicts": conflicts,
        "causal_links": causal_links, "thread_lifecycle": thread_lifecycle,
        "approved_evidence_count": len(records),
        "pending_proposals_visible": sum(
            1 for row in canon.list_facts(series_id, status="proposed")
            if row["reference"]["book"] <= book
            and (row["start_book"], row["start_sequence"]) <= (book, sequence)
            and (not subject_id or row["subject_id"] == subject_id
                 or row["object_entity_id"] == subject_id
                 or row["knower_id"] == subject_id)
        ),
        "evidence_only": True, "model_called": False,
        "limitations": [
            "Unapproved and future-book assertions are not used as knowledge.",
            "Source citations prove where text appears, not author intent or psychological causality.",
            "Scene sequence is assigned by authors; imported EPUBs do not automatically establish in-world chronology.",
            "Contradiction checks compare only approved, explicitly single-valued predicates; silence is not a contradiction.",
        ],
    }
    response["answer_status"] = "grounded" if records else "insufficient_approved_evidence"
    return response
