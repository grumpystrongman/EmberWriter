"""One source-backed, point-in-time read model for Series Vault consumers.

Manuscripts and approved canon remain authoritative. This module never writes,
guesses a character's psychology, or promotes a proposed fact. Every projected
claim retains its immutable manuscript citation.
"""
from __future__ import annotations

from collections import defaultdict

from . import series_canon as canon
from . import series_vault as vault

PSYCHOLOGY = {
    "goals": {"wants", "goal", "seeks", "desires", "needs", "intends", "motivation"},
    "fears": {"fears", "fear", "avoids", "dreads", "wound", "trauma"},
    "secrets": {"hides", "secret", "conceals", "secret_from", "knows"},
    "voice": {"speaks_like", "speech_style", "voice", "dialogue_style"},
    "identity": {"identity", "role", "believes", "values", "vulnerability"},
}
THREAD_START = {"foreshadows", "setup_for", "promises", "introduces_thread", "plants", "mystery"}
THREAD_PAYOFF = {"pays_off", "resolves", "fulfills", "answers"}
THREAD_SIGNAL = {"reveals", "discovers"}
RELATIONSHIPS = {
    "trusts", "distrusts", "loves", "fears", "protects", "betrays",
    "allied_with", "rivals", "bonded_to", "related_to", "works_with",
}


def _applies(fact: dict, book: int, sequence: int) -> bool:
    # A proposal based on a later source is never eligible for earlier books.
    if fact["reference"]["book"] > book:
        return False
    if (fact["start_book"], fact["start_sequence"]) > (book, sequence):
        return False
    return not (fact["end_book"] is not None and (fact["end_book"], fact["end_sequence"] if fact["end_sequence"] is not None else 999999) < (book, sequence))


def story_state(series_id: str, book: int, sequence: int = 999999) -> dict:
    """Inspect the accepted universe with distinct world/reader/character lenses."""
    if not 0 <= sequence <= 999999:
        raise ValueError("Scene sequence must be between 0 and 999999")
    series = vault.series_detail(series_id)
    volumes = series["volumes"]
    if not any(item["ordinal"] == book for item in volumes):
        raise ValueError("Choose an existing book in this series")

    entities = canon.list_entities(series_id)
    # One indexed read for the entire approved series, not one DB connection
    # per character. This keeps story time scrubbing usable with large casts.
    all_facts = canon.list_facts(series_id)
    sequence_points = sorted({0, 999999, *(fact["start_sequence"] for fact in all_facts
                                              if fact["start_book"] == book)})
    accepted = [fact for fact in all_facts
                if fact["status"] == "approved" and _applies(fact, book, sequence)]
    accepted.sort(key=lambda item: (
        item["start_book"], item["start_sequence"], item["created_at"], item["id"]
    ))
    proposals = [fact for fact in all_facts
                 if fact["status"] == "proposed" and _applies(fact, book, sequence)]
    groups: dict[tuple[str, str, str, str], list[dict]] = defaultdict(list)
    for fact in accepted:
        groups[(fact["subject_id"], fact["predicate"],
                fact["scope"], fact["knower_id"] or "")].append(fact)
    conflicts = []
    for rows in groups.values():
        values = {(row["object_entity_id"], row["object_text"]) for row in rows}
        if len(values) > 1 and rows[0]["predicate"] in canon.EXCLUSIVE_PREDICATES:
            conflicts.append({
                "subject": rows[0]["subject_name"], "predicate": rows[0]["predicate"],
                "scope": rows[0]["scope"], "knower_id": rows[0]["knower_id"],
                "assertion_ids": [row["id"] for row in rows],
                "note": "Competing approved assertions; author review required",
            })
    by_entity: dict[str, list[dict]] = defaultdict(list)
    for fact in accepted:
        by_entity[fact["subject_id"]].append(fact)
        if fact["knower_id"] and fact["knower_id"] != fact["subject_id"]:
            by_entity[fact["knower_id"]].append(fact)
    profiles = {}
    for entity in entities:
        related = by_entity[entity["id"]]
        facets = {
            facet: [fact for fact in related if
                    fact["subject_id"] == entity["id"] and fact["predicate"].lower() in terms]
            for facet, terms in PSYCHOLOGY.items()
        }
        profiles[entity["id"]] = {
            "entity_id": entity["id"], "name": entity["name"], "kind": entity["kind"],
            "facts": related, "facets": facets,
            "observed_as_of_book": book,
            "missing_facets": [
                facet for facet, evidence in facets.items()
                if not evidence and entity["kind"] == "character"
            ],
        }

    links = []
    for fact in accepted:
        if not fact["object_entity_id"]:
            continue
        links.append({
            "from": fact["subject_id"], "to": fact["object_entity_id"],
            "predicate": fact["predicate"], "fact_id": fact["id"],
            "relationship": fact["predicate"].lower() in RELATIONSHIPS,
            "scope": fact["scope"], "knower_id": fact["knower_id"],
            "reference": fact["reference"],
        })

    # Threads aren't inferred from narrative mood. They require explicit, cited
    # assertions and can therefore be explained and corrected by the author.
    thread_rows: dict[str, list[dict]] = defaultdict(list)
    for fact in accepted:
        if fact["predicate"].lower() in THREAD_START | THREAD_PAYOFF | THREAD_SIGNAL:
            thread_rows[fact["subject_id"]].append(fact)
    threads = []
    entity_by_id = {entity["id"]: entity for entity in entities}
    for entity_id, events in thread_rows.items():
        entity = entity_by_id.get(entity_id)
        last = events[-1]
        has_setup = any(row["predicate"].lower() in THREAD_START for row in events)
        has_payoff = any(row["predicate"].lower() in THREAD_PAYOFF for row in events)
        threads.append({
            "entity_id": entity_id, "name": entity["name"] if entity else last["subject_name"],
            "status": "resolved" if has_payoff else ("open" if has_setup else "unanchored"),
            "unearned_payoff": has_payoff and not has_setup,
            "unanchored_reveal": not has_setup and not has_payoff,
            "events": events,
        })

    stale_sources = []
    for volume in volumes:
        if not volume.get("project_slug"):
            continue
        for source in vault.volume_sources(series_id, volume["id"]):
            if source.get("linked_project_changed"):
                stale_sources.append({
                    "source_id": source["id"], "source_path": source["source_path"],
                    "book": volume["ordinal"], "volume": volume["title"],
                    "reason": "Linked manuscript changed since the preserved evidence snapshot",
                })

    return {
        "series_id": series_id, "book": book, "sequence": sequence,
        "sequence_points": sequence_points,
        "stale_sources": stale_sources,
        "volumes": [{"id": row["id"], "title": row["title"], "ordinal": row["ordinal"]}
                    for row in volumes],
        "entities": entities,
        "facts": accepted, "proposals": proposals,
        "conflicts": conflicts, "profiles": profiles, "links": links,
        "threads": threads,
        "limits": {
            "model_inference": False,
            "psychology": "Only source-backed predicates explicitly approved by the author",
            "threads": "Only source-backed setup and payoff predicates",
            "proposals": "Never treated as established canon",
            "chronology": "Book order and source sequence, not absolute in-world calendar dates",
        },
    }
