"""50 deterministic cross-book knowledge answers on synthetic author-approved facts.

These are machine-defined regression cases, not independent human reviews of
a copyrighted novel. They certify exact provenance and spoiler cutoffs only.
"""
from __future__ import annotations

import pytest

from app import series_canon as canon
from app import series_knowledge_lab as lab
from app import series_vault as vault
from app import storage


@pytest.fixture(scope="module")
def golden_approved_series(tmp_path_factory):
    # The isolated root is restored after this module, so no author data leaks.
    original = storage.PROJECTS_ROOT
    storage.PROJECTS_ROOT = tmp_path_factory.mktemp("knowledge-golden") / "projects"
    try:
        series_id = vault.create_series("Synthetic Fifty Claims")["id"]
        names = [f"Traveller {index:02d}" for index in range(10)]
        entities = [canon.add_entity(series_id, name, "character") for name in names]
        for book in range(1, 6):
            prose = " ".join(
                f"Traveller {person:02d} resides in Chamber {book}-{person:02d}."
                for person in range(10)
            )
            vault.import_volume(
                series_id, f"synthetic-{book}.md", prose.encode("utf-8"), book,
                title=f"Synthetic Book {book}", kind="novel",
                edition_status="reference", rights_confirmed=True,
            )
            source_id = vault.series_detail(series_id)["volumes"][-1]["sources"][0]["id"]
            for person, subject in enumerate(entities):
                line = f"Traveller {person:02d} resides in Chamber {book}-{person:02d}."
                start = prose.index(line)
                candidate = canon.propose_fact(
                    series_id, subject["id"], "located_in",
                    object_text=f"Chamber {book}-{person:02d}",
                    start_book=book, end_book=book,
                    source_id=source_id, quote_start=start,
                    quote_end=start + len(line), quote=line,
                )
                canon.review_fact(series_id, candidate["id"], "approved")
        yield series_id, entities
    finally:
        storage.PROJECTS_ROOT = original


@pytest.mark.parametrize("book,person", [
    (book, person) for book in range(1, 6) for person in range(10)
])
def test_fifty_book_character_questions_with_grounded_answers(golden_approved_series, book, person):
    series_id, entities = golden_approved_series
    observation = lab.investigate(series_id, book, subject_id=entities[person]["id"])
    active = observation["world_truths"]
    assert len(active) == 1
    claim = active[0]
    assert claim["value"] == f"Chamber {book}-{person:02d}"
    assert claim["citation"]["book"] == book
    assert claim["citation"]["quote"] == (
        f"Traveller {person:02d} resides in Chamber {book}-{person:02d}."
    )
    assert observation["possible_conflicts"] == []
    # The public current-state lens cannot reveal past or future locations.
    assert not any(row["value"].startswith(f"Chamber {book+1}-") for row in active)
    assert observation["model_called"] is False
