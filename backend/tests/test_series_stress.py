"""Synthetic scalability gates: 12-volume series and a thousand-character cast.

The test writes to pytest's isolated tmp_path only. It never opens the user's
local manuscript or external model. This is a deterministic read model stress
test, not a substitute for the browser/real-world accessibility test.
"""
from __future__ import annotations

from pathlib import Path
from time import perf_counter

import pytest

from app import series_story_state as state
from app import series_vault as vault
from app import storage


def test_large_cast_time_machine_stays_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    sid = vault.create_series("Synthetic Twelve-Book Memory")["id"]
    volumes = []
    quote = "Keeper guards the crystalline vault."
    for n in range(1,13):
        volume = vault.import_volume(
            sid, f"book-{n}.md", (quote + "\n").encode(), n,
            title=f"Volume {n}", kind="novel", edition_status="approved",
            rights_confirmed=True,
        )
        volumes.append(volume)
    sources = [v["sources"][0]["id"] for v in vault.series_detail(sid)["volumes"]]
    with vault._connect() as con:
        entities = []
        for n in range(1000):
            entity_id = vault._id()
            entities.append(entity_id)
            con.execute(
                "INSERT INTO entities (id,series_id,name,kind,aliases,description,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (entity_id, sid, f"Keeper {n:04d}", "character", "[]", "", vault.now()),
            )
        for n in range(2400):
            book = n % 12 + 1
            con.execute("""
                INSERT INTO assertions (
                  id,series_id,subject_id,predicate,object_text,scope,
                  start_book,start_sequence,source_id,quote_start,quote_end,quote,
                  status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                vault._id(), sid, entities[n%1000], "guards",
                "the crystalline vault", "world", book, 1, sources[book-1],
                0, len(quote), quote, "approved", vault.now(),
            ))
    t0 = perf_counter()
    book_one = state.story_state(sid, 1)
    t1 = perf_counter()
    book_twelve = state.story_state(sid, 12)
    t2 = perf_counter()
    assert len(book_one["entities"]) == 1000
    assert len(book_twelve["entities"]) == 1000
    assert len(book_twelve["facts"]) == 2400
    assert len(book_one["facts"]) == 200
    assert all(fact["reference"]["book"] <= 1 for fact in book_one["facts"])
    assert not book_twelve["conflicts"]
    assert t1-t0 < 10, f"Book 1 projection exceeded budget: {t1-t0:.2f}s"
    assert t2-t1 < 10, f"Book 12 projection exceeded budget: {t2-t1:.2f}s"
    print(f"12-book/1000-entity/2400-assertion read: {t1-t0:.3f}s, {t2-t1:.3f}s")
