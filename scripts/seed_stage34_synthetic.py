"""Seed a fresh, strictly isolated synthetic writer browser fixture.

Never call against the normal author data directory. No copyrighted content.
"""
from __future__ import annotations

import os
from pathlib import Path

from app import series_canon, series_scene_studio, series_vault, storage


def main() -> None:
    data = Path(os.environ["EMBER_DATA_DIR"]).resolve()
    if data.name != "Stage34-Fresh-Synthetic-QA" or not data.parent.name == "EmberWriter-Stage34-LocalEvidence":
        raise RuntimeError("Refusing to seed any non-QA data directory")
    if data.exists() and any(data.iterdir()):
        raise RuntimeError("Use a fresh isolated QA directory; refusing existing data")
    project = storage.create_project("The Ashen Coast - Synthetic Editorial Review", "Test data only")
    storage.save_text(project["slug"], "manuscript/chapter-001.md",
                      "# The Letter Beneath the Door\n\n"
                      "The keeper found a lantern and an unsigned note.\n\n"
                      "They agreed to inspect the harbor before dusk.\n")
    series = series_vault.create_series("The Astral Lanterns",
                                      "Synthetic three-book fantasy chronicle for interface testing only")
    series_vault.import_volume(series["id"], "synthetic-book-1.md",
        b"# The Lantern Trial\n\nMara and Kael enter the quiet harbor.\n",
        1, title="The Lantern Trial", kind="novel",
        edition_status="approved", rights_confirmed=True)
    mara = series_canon.add_entity(series["id"], "Mara", "character")
    kael = series_canon.add_entity(series["id"], "Kael", "character")
    harbor = series_canon.add_entity(series["id"], "Glass Harbor", "place")
    series_scene_studio.create_board(series["id"], {
        "title": "The Harbor Letter", "book": 1, "sequence": 1,
        "objective": "Find the hidden message", "conflict": "The lantern has gone dark",
        "opening": "The two friends enter the harbor",
        "aftermath": "They will search the lighthouse",
        "voice_notes": "Restrained dialogue",
        "pov_id": mara["id"], "location_id": harbor["id"],
        "participants": [mara["id"], kael["id"]],
        "beats": [
            {"id": "b01", "kind": "arrival", "title": "Enter harbor", "detail": "The bell rings", "pressure": 20},
            {"id": "b02", "kind": "reversal", "title": "Open note", "detail": "A warning is revealed", "pressure": 75},
        ],
    })
    # Re-open through public library reads to exercise immutable source hashes.
    detail = series_vault.series_detail(series["id"])
    assert len(detail["volumes"]) == 1
    source = detail["volumes"][0]["sources"][0]
    series_vault.source_text(series["id"], source["id"])
    assert len(series_scene_studio.list_boards(series["id"])) == 1
    print("STAGE34_ISOLATED_FIXTURE_READY")


if __name__ == "__main__":
    main()
