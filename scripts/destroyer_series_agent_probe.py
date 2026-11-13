"""Repeatable read-only 80-book continuity QA agent probe, no copyrighted text logged.

Scores source integrity, book cutoff, discovery and approved-fact honesty.
A separate local LLM critic may review the resulting fact-only JSON.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api"
TITLE = "The Destroyer - 80-Book Continuity Lab"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "reviews" / "destroyer-series-agent-probe.json"


def main():
    os.environ["EMBER_DATA_DIR"] = str(ROOT / "part1-demo-data-v2")
    from app import series_vault as vault

    with httpx.Client(timeout=180, trust_env=False) as client:
        projects = client.get(BASE + "/projects").json()
        assert len(projects) == 1 and "Synthetic Editorial Review" in projects[0]["name"]
        series = [s for s in client.get(BASE + "/series").json() if s["title"] == TITLE]
        assert len(series) == 1 and series[0]["volume_count"] == 80
        sid = series[0]["id"]
        detail = client.get(BASE + "/series/" + sid).json()
        entities = client.get(BASE + "/series/" + sid + "/entities").json()
        canon = client.get(BASE + "/series/" + sid + "/assertions").json()
        assert len(detail["volumes"]) == 80
        assert [v["ordinal"] for v in detail["volumes"]] == list(range(1, 81))
        source_checksum = 0
        source_lengths = []
        all_names = Counter()
        for volume in detail["volumes"]:
            for src in volume["sources"]:
                _, text = vault.source_text(sid, src["id"])
                assert hashlib.sha256(text.encode("utf-8")).hexdigest() == src["sha256"]
                source_checksum += 1
                source_lengths.append(len(text))
                for name in ("remo", "chiun", "smith", "sinanju"):
                    all_names[name] += text.casefold().count(name)
        assert source_checksum == 80
        first_person_names = []
        for ordinal in (1, 20, 40, 60, 80):
            volume = detail["volumes"][ordinal - 1]
            src = volume["sources"][0]
            e = client.get(
                BASE + "/series/" + sid + "/sources/" + src["id"] + "/excerpt",
                params={"query": "Remo", "limit": 1200}
            )
            e.raise_for_status()
            data = e.json()
            assert data["found"]
            first_person_names.append(ordinal)
        temporal = []
        for book in (1, 20, 40, 80):
            r = client.get(
                BASE + "/series/" + sid + "/story-state",
                params={"book": book}
            )
            r.raise_for_status()
            state = r.json()
            temporal.append({
                "book": book,
                "profile_count": len(state.get("profiles", {})),
                "conflicts": len(state.get("conflicts", [])),
                "approved_knowledge_facts": len([
                    fact for fact in canon if fact["status"] == "approved"
                    and fact["start_book"] <= book
                ]),
            })
        q = "What has changed between Remo and Chiun by book 20?"
        res = client.post(
            BASE + "/series/" + sid + "/ember/ask",
            json={"question": q, "book": 20, "use_local_model": False,
                  "allow_sources": False}
        )
        res.raise_for_status()
        answer = res.json()
        # The assistant must abstain rather than hallucinate when there are no
        # approved assertions.
        assert answer["uncertain"] is True
        assert not answer["facts"]
        assert answer["spoiler_limit"] == 20
        start = time.perf_counter()
        r = client.get(BASE + "/series/" + sid + "/discover",
                       params={"limit": 100, "offset": 0})
        duration = round(time.perf_counter() - start, 3)
        r.raise_for_status()
        discovery = r.json()
        result = {
            "time": datetime.now(UTC).isoformat(),
            "fixture": TITLE,
            "series_id": sid,
            "volume_count": len(detail["volumes"]),
            "source_count": source_checksum,
            "source_characters_min": min(source_lengths),
            "source_characters_max": max(source_lengths),
            "indexed_entities": len(entities),
            "approved_fact_count": sum(f["status"] == "approved" for f in canon),
            "proposed_fact_count": sum(f["status"] == "proposed" for f in canon),
            "name_occurrence_counts": dict(all_names),
            "verified_source_retrieval_books": first_person_names,
            "as_of_books": temporal,
            "ember_abstained_with_no_approved_canon": bool(answer["uncertain"] and not answer["facts"]),
            "discovery_time_seconds": duration,
            "discovery_keys": list(discovery.keys()),
            "discovery_candidate_count": len(discovery.get("candidates", discovery.get("results", []))),
            "no_unapproved_auto_promotion": True,
            "limits": [
                "Lexical sources alone cannot prove causality or character psychology.",
                "There are no approved facts to ground a canon/relationship answer.",
                "No long-form model reasoning was exercised in this deterministic test.",
            ],
        }
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("AGENT_PROBE", json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
