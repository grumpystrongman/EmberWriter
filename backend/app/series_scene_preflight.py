"""Evidence-driven scene preflight: explicit staging and character state only.

Not a travel simulator: differing last-known locations are prompts to check the
manuscript, not claims of physically impossible travel. No canon is modified.
"""
from __future__ import annotations

from . import series_canon as canon
from . import series_scene_studio as studio
from . import series_story_state as state

LOCATION = {"located_in", "at", "stays_in", "trapped_in", "resides_in"}
INJURY = {"injured", "wounded", "exhausted", "cursed", "recovering_from", "cannot_use"}
RELATION = {"distrusts", "betrays", "rivals", "sets_boundary_with", "forgives", "trusts",
            "protects", "consents_to", "owes", "fears"}
ITEM = {"holds", "carries", "possesses", "keeps", "lost", "stole"}


def preflight(series_id: str, payload: dict) -> dict:
    scene = studio._validate(series_id, payload)
    entity_list = canon.list_entities(series_id)
    entities = {entity["id"]: entity for entity in entity_list}
    accepted = [
        fact for fact in canon.list_facts(series_id, status="approved")
        if state._applies(fact, scene["book"], scene["sequence"])
    ]
    participants = set(scene["participants"])
    checks = []
    for participant_id in scene["participants"]:
        name = entities[participant_id]["name"]
        subject = [fact for fact in accepted if fact["subject_id"] == participant_id
                   and fact["scope"] == "world"]
        subject.sort(key=lambda fact: (fact["start_book"], fact["start_sequence"],
                                       fact["created_at"], fact["id"]))
        locations = [fact for fact in subject if fact["predicate"] in LOCATION]
        if locations and scene["location_id"]:
            latest = locations[-1]
            planned = entities[scene["location_id"]]["name"]
            last = latest["object_name"] or latest["object_text"]
            same = (latest["object_entity_id"] == scene["location_id"] or
                    last.casefold() == planned.casefold())
            if not same:
                checks.append({
                    "category": "staging", "level": "check",
                    "title": f"Verify {name}'s travel to {planned}",
                    "reason": f"The latest cited location is {last}. The scene is planned at {planned}; travel may have happened off-page.",
                    "fact_id": latest["id"], "reference": latest["reference"],
                    "quote": latest["quote"], "subject_id": participant_id,
                })
        for fact in subject:
            if fact["predicate"] in INJURY:
                checks.append({
                    "category": "condition", "level": "context",
                    "title": f"{name}: {fact['predicate'].replace('_',' ')}",
                    "reason": "Account for this accepted condition if it is still relevant to the scene.",
                    "fact_id": fact["id"], "reference": fact["reference"],
                    "quote": fact["quote"], "subject_id": participant_id,
                })
            if fact["predicate"] in ITEM:
                checks.append({
                    "category": "inventory", "level": "context",
                    "title": f"{name}: {fact['predicate'].replace('_',' ')} {fact['object_name'] or fact['object_text']}",
                    "reason": "Referenced possession or artifact state is part of the accepted story.",
                    "fact_id": fact["id"], "reference": fact["reference"],
                    "quote": fact["quote"], "subject_id": participant_id,
                })
            if fact["predicate"] in RELATION and fact["object_entity_id"] in participants:
                checks.append({
                    "category": "relationship", "level": "context",
                    "title": f"{name} {fact['predicate'].replace('_',' ')} {fact['object_name']}",
                    "reason": "Keep this accepted relationship state in mind; it does not determine anyone's consent or actions.",
                    "fact_id": fact["id"], "reference": fact["reference"],
                    "quote": fact["quote"], "subject_id": participant_id,
                })
    # One source-backed occurrence per kind/predicate/value and scene subject.
    seen = set()
    distinct = []
    for check in reversed(checks):
        key = (check["category"], check["subject_id"], check["title"])
        if key not in seen:
            seen.add(key)
            distinct.append(check)
    distinct.reverse()
    return {
        "series_id": series_id, "book": scene["book"], "sequence": scene["sequence"],
        "planned_location": entities[scene["location_id"]]["name"] if scene["location_id"] else None,
        "participants": [entities[eid]["name"] for eid in scene["participants"]],
        "checks": distinct[:40], "total_checks": len(distinct),
        "staging_flags": sum(x["category"] == "staging" for x in distinct),
        "limitations": "Only source-linked, author-approved facts at this book and scene position. "
                       "A travel prompt is not proof of impossible movement. Undocumented conditions, "
                       "consent and emotional changes cannot be safely inferred.",
        "read_only": True, "canon_modified": False,
    }
