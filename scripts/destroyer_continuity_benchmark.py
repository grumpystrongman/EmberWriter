"""Local 80-volume source-continuity search benchmark with no text or quotes logged."""
from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000/api"
SERIES_TITLE = "The Destroyer - 80-Book Continuity Lab"
OUTPUT = ROOT / "docs" / "reviews" / "destroyer-80-book-search-benchmark.json"


def main():
    with httpx.Client(timeout=240.0, trust_env=False) as client:
        projects = client.get(BASE + "/projects").json()
        assert len(projects) == 1 and "Synthetic Editorial Review" in projects[0]["name"]
        listing = client.get(BASE + "/series").json()
        matching = [item for item in listing if item["title"] == SERIES_TITLE]
        assert len(matching) == 1
        series_id = matching[0]["id"]
        detail = client.get(BASE + "/series/" + series_id).json()
        assert len(detail["volumes"]) == 80
        checks = [
            ("Remo", 80),
            ("Chiun", 80),
            ("Sinanju", 80),
            ("CURE", 80),
            ("Smith", 80),
            ("Remo Chiun", 80),
            ("Remo", 20),
            ("Remo", 1),
            ("definitelynotinthebooks987", 80),
        ]
        results = []
        for query, max_book in checks:
            begin = time.perf_counter()
            response = client.get(
                BASE + "/series/" + series_id + "/evidence-search",
                params={"query": query, "max_book": max_book, "limit": 20},
            )
            duration = round(time.perf_counter() - begin, 3)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Search {query}/{max_book} failed with {response.status_code}: "
                    + response.text[:300]
                )
            report = response.json()
            assert all(1 <= r["book"] <= max_book for r in report["results"])
            if query.startswith("definitely"):
                assert report["total_hits"] == 0
            results.append({
                "query": query,
                "max_book": max_book,
                "elapsed_seconds": duration,
                "total_matching_windows": report["total_hits"],
                "returned_results": len(report["results"]),
                "book_ordinals_sample": [r["book"] for r in report["results"][:8]],
            })
            print("SEARCH",
                  json.dumps(results[-1], ensure_ascii=False), flush=True)
        output = {
            "time": datetime.now(UTC).isoformat(),
            "series_id": series_id,
            "book_count": 80,
            "source_count": 80,
            "method": "Offline SQLite FTS5 exact source windows, current test site",
            "measurements": results,
            "verified_no_future_book_leakage": True,
            "semantic_facts_automatically_approved": False,
            "notice": "Literal source retrieval, not psychological or causal narrative inference.",
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(output, indent=2), encoding="utf-8")
        print("RESULT", OUTPUT)


if __name__ == "__main__":
    main()
