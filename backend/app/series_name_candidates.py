"""Review-only capitalized-name leads across immutable source snapshots.

A capitalized word is not necessarily a person. Confidence here means
repeated textual occurrence only, not character identity or canon truth.
"""
from __future__ import annotations

# A readable stopword lexicon is more maintainable than a 100-item list literal.
# ruff: noqa: SIM905
import re

from . import series_canon as canon
from . import series_vault as vault

NAME = re.compile(r"(?<![\w])([A-Z][a-z]{2,}(?:[ \t]+[A-Z][a-z]{2,}){0,2})(?![\w])")
STOP = frozenset("""
The This That There Then These Those While Before After During Until However
Here Today Yesterday Tomorrow Chapter Book Part One Two Three Four Five Six
Seven Eight Nine Ten Eleven Twelve Sunday Monday Tuesday Wednesday Thursday
Friday Saturday January February March April May June July August September
October November December Suddenly Meanwhile Later Earlier Nothing Something
Someone Everyone Anybody Nobody Once Never Always Sometimes It Its His Her
She He They Them We You Your I My Me Our Their In On At Of By To For
From And But Or Yet So No Yes Not A An What When Where Why How Which Who
Oh Ah Well Please Perhaps Maybe Now Though Since Because As If Even
First Second Third Fourth Fifth Last Next End Beginning Continued
South North East West America American United States New York
""".split())
MAX_EXAMPLES = 2
MAX_NAME_LENGTH = 75
MAX_CANDIDATES = 100
MAX_SCAN_MATCHES = 2_000_000


def propose(series_id: str, *, limit: int = 60,
            min_books: int = 2, query: str = "") -> dict:
    if not 1 <= limit <= MAX_CANDIDATES or not 1 <= min_books <= 80 or len(query) > 80:
        raise ValueError("Invalid candidate name search bounds")
    query = query.strip().casefold()
    detail = vault.series_detail(series_id)
    existing = canon.list_entities(series_id)
    known = {value.strip().casefold() for entity in existing
             for value in [entity["name"], *entity.get("aliases", [])]}
    known_tokens = {fragment.casefold() for form in known
                    for fragment in form.split() if len(fragment) >= 3}
    counters: dict[str, dict] = {}
    scanned = 0
    inspected = 0
    for volume in detail["volumes"]:
        for source in volume["sources"]:
            record, content = vault.source_text(series_id, source["id"])
            scanned += 1
            for match in NAME.finditer(content):
                inspected += 1
                if inspected > MAX_SCAN_MATCHES:
                    break
                label = match.group(1)
                if len(label) > MAX_NAME_LENGTH:
                    continue
                tokens = label.split()
                if not tokens or any(token in STOP for token in tokens):
                    continue
                key = label.casefold()
                if key in known or (len(tokens) == 1 and key in known_tokens):
                    continue
                # Single capitalized words at a sentence boundary are usually
                # ordinary grammar, not evidence of a named character.
                if len(tokens) == 1:
                    prior = content[max(0, match.start()-5):match.start()].rstrip()
                    if not prior or prior[-1] in ".!?\n:\u201c\u201d\"":
                        continue
                state = counters.setdefault(key, {
                    "label": label, "count": 0, "books": set(),
                    "samples": [],
                })
                state["count"] += 1
                state["books"].add(volume["ordinal"])
                if len(state["samples"]) < MAX_EXAMPLES:
                    left = max(0, match.start()-75)
                    right = min(len(content), match.end()+125)
                    state["samples"].append({
                        "book": volume["ordinal"], "source_id": source["id"],
                        "source_hash": record["sha256"],
                        "start": match.start(), "end": match.end(),
                        "excerpt_start": left, "excerpt_end": right,
                        "excerpt": content[left:right],
                    })
            if inspected > MAX_SCAN_MATCHES:
                break
        if inspected > MAX_SCAN_MATCHES:
            break
    candidates = []
    for key, item in counters.items():
        if len(item["books"]) < min_books or (query and query not in key):
            continue
        if item["count"] < (15 if " " not in key else 5):
            continue
        candidates.append({
            "label": item["label"], "literal_mention_count": item["count"],
            "books_with_mention": len(item["books"]),
            "sample_books": sorted(item["books"])[:12],
            "samples": item["samples"],
            "status": "unreviewed_capitalization_candidate",
            "character_identity_verified": False,
        })
    candidates.sort(key=lambda row: (-row["books_with_mention"],
                                    -row["literal_mention_count"], row["label"]))
    return {
        "series_id": series_id, "scanned_sources": scanned,
        "query": query,
        "total_candidates": len(candidates), "candidates": candidates[:limit],
        "truncated": inspected > MAX_SCAN_MATCHES,
        "automatically_created_entities": 0,
        "disclaimer": (
            "Capitalization and frequency are search hints, never evidence of a "
            "character. Names may be places, titles, ordinary words, false identities "
            "or OCR noise. Review the exact passage before adding an entity."
        ),
    }
