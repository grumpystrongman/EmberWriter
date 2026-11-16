"""User-authorized, local-only Destroyer continuity benchmark fixture.
Runs solely against the pre-existing isolated EmberWriter test server on localhost.
No EPUB/source text is written to Git, transmitted externally or printed.
"""
from __future__ import annotations

import json
import re
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000/api"
TITLE = "The Destroyer - 80-Book Continuity Lab"
ARCHIVE = Path.home() / "Downloads" / "The Destroyer ePub eBooks murphy sapir remo.zip"
REPORT = Path(__file__).resolve().parents[1] / "docs" / "reviews" / "destroyer-80-book-import-evidence.json"


def main() -> None:
    if not ARCHIVE.is_file():
        raise RuntimeError("User-provided local EPUB archive is not present")
    with zipfile.ZipFile(ARCHIVE) as z:
        members = [entry for entry in z.infolist() if entry.filename.lower().endswith(".epub")]
        indexes = sorted(
            int(re.search(r"Destroyer\s+(\d+)", e.filename, re.I).group(1))
            for e in members
        )
        assert indexes == list(range(1, 81)), "Only the verified 1-80 collection may be used"
    with httpx.Client(timeout=240.0, trust_env=False) as client:
        projects_response = client.get(BASE + "/projects")
        projects_response.raise_for_status()
        projects = projects_response.json()
        if len(projects) != 1 or "Synthetic Editorial Review" not in projects[0]["name"]:
            raise RuntimeError("Safety gate: not the isolated synthetic test site")
        listing = client.get(BASE + "/series").json()
        matching = [item for item in listing if item["title"] == TITLE]
        if len(matching) > 1:
            raise RuntimeError("Multiple test series already exist; manual reconciliation required")
        if matching:
            identifier = matching[0]["id"]
            print("Reusing existing isolated series", identifier)
        else:
            created = client.post(BASE + "/series", json={
                "title": TITLE,
                "description": "Private local reference corpus for 80-volume scale, source and continuity evaluation. No manuscript edits or automatic canon."
            })
            created.raise_for_status()
            identifier = created.json()["id"]
            print("Created isolated reference series", identifier)
        detail = client.get(f"{BASE}/series/{identifier}").json()
        elapsed = None
        imported = None
        if len(detail["volumes"]) == 0:
            start = time.perf_counter()
            with ARCHIVE.open("rb") as stream:
                result = client.post(
                    f"{BASE}/series/{identifier}/volumes/bulk-zip",
                    data={"rights_confirmed": "true"},
                    files={"file": (ARCHIVE.name, stream, "application/zip")},
                )
            elapsed = round(time.perf_counter() - start, 3)
            if result.status_code != 201:
                raise RuntimeError("Bulk import failed " + str(result.status_code) + ": " + result.text[:600])
            imported = result.json()
            print("HTTP import completed", imported["imported_count"], "volumes in", elapsed, "seconds")
        detail = client.get(f"{BASE}/series/{identifier}").json()
        volumes = detail["volumes"]
        assert len(volumes) == 80, f"Expected 80 source volumes, found {len(volumes)}"
        assert [v["ordinal"] for v in volumes] == list(range(1, 81))
        assert all(v["edition_status"] == "reference" for v in volumes)
        assert all(v["source_count"] == 1 for v in volumes)
        assert all(v["project_slug"] is None for v in volumes)
        sample_offsets = {}
        for position in (1, 20, 40, 60, 80):
            volume = volumes[position - 1]
            source = volume["sources"][0]
            excerpt = client.get(
                f"{BASE}/series/{identifier}/sources/{source['id']}/excerpt",
                params={"query": "Remo", "limit": 1200}
            )
            excerpt.raise_for_status()
            result = excerpt.json()
            sample_offsets[str(position)] = {
                "book_title": volume["title"],
                "source_sha256": source["sha256"],
                "finds_name": result["found"],
                "source_characters": result["total_characters"] if result["found"] else None,
                "excerpt_offset": result.get("excerpt_start"),
            }
            # The source text is intentionally NEVER logged or persisted to report.
        snapshot = {
            "timestamp": datetime.now(UTC).isoformat(),
            "archive_path": str(ARCHIVE),
            "import_mode": "local HTTP bulk ZIP upload into isolated test Series Vault",
            "series_id": identifier,
            "series_title": TITLE,
            "books": len(volumes),
            "ordinal_min": volumes[0]["ordinal"],
            "ordinal_max": volumes[-1]["ordinal"],
            "source_count": sum(v["source_count"] for v in volumes),
            "extracted_bytes": sum(s["bytes"] for v in volumes for s in v["sources"]),
            "elapsed_seconds": elapsed,
            "source_checks": sample_offsets,
            "approved_canon_count": 0,
            "original_projects_untouched": True,
            "books_auto_approved": False,
            "limitations": "Book import and string retrieval are not semantic psychology or continuity proof."
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        print("RESULT", json.dumps({
            key: snapshot[key] for key in (
                "series_id", "series_title", "books", "source_count",
                "extracted_bytes", "elapsed_seconds", "approved_canon_count"
            )
        }, ensure_ascii=False))
        print("PRIVATE EVIDENCE:", REPORT)


if __name__ == "__main__":
    main()
