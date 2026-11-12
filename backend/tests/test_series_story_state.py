"""Synthetic-only acceptance contracts for unified story state."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_story_state
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def universe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    series = vault.create_series("Synthetic Aurora")
    texts = [
        "Ada trusts Bex. Ada fears the river. The silver bell foreshadows the final siege.",
        "Ada stops trusting Bex. Bex reveals the hidden bell. The bell resolves the siege.",
    ]
    for index, text in enumerate(texts, 1):
        vault.import_volume(
            series["id"], f"book{index}.md", text.encode(), index,
            title=f"Book {index}", kind="novel", edition_status="approved",
            rights_confirmed=True,
        )
    volumes = vault.series_detail(series["id"])["volumes"]
    ada = canon.add_entity(series["id"], "Ada", "character")
    bex = canon.add_entity(series["id"], "Bex", "character")
    bell = canon.add_entity(series["id"], "Bell", "artifact")

    def propose(book, subject, predicate, phrase, obj="", target=None, scope="world",
                knower_id=None):
        text = texts[book - 1]
        start = text.index(phrase)
        return canon.propose_fact(
            series["id"], subject["id"], predicate,
            object_text=obj, object_entity_id=target["id"] if target else None,
            scope=scope, knower_id=knower_id, start_book=book,
            source_id=volumes[book - 1]["sources"][0]["id"],
            quote_start=start, quote_end=start + len(phrase), quote=phrase,
        )

    p1 = propose(1, ada, "trusts", "Ada trusts Bex.", target=bex)
    canon.review_fact(series["id"], p1["id"], "approved")
    p2 = propose(1, ada, "fears", "Ada fears the river.", obj="river")
    canon.review_fact(series["id"], p2["id"], "approved")
    p3 = propose(1, bell, "foreshadows", "The silver bell foreshadows the final siege.", obj="final siege")
    canon.review_fact(series["id"], p3["id"], "approved")
    p4 = propose(2, bell, "resolves", "The bell resolves the siege.", obj="siege")
    canon.review_fact(series["id"], p4["id"], "approved")
    p5 = propose(2, bex, "reveals", "Bex reveals the hidden bell.", obj="hidden bell", scope="reader_reveal")
    canon.review_fact(series["id"], p5["id"], "approved")
    p6 = propose(2, ada, "distrusts", "Ada stops trusting Bex.", target=bex)
    return series["id"], ada["id"], bex["id"], bell["id"], p6["id"]


def test_point_in_time_never_leaks_future_knowledge(universe):
    series_id, ada, bex, bell, pending_id = universe
    first = series_story_state.story_state(series_id, 1)
    assert first["profiles"][ada]["facets"]["fears"][0]["object_text"] == "river"
    assert first["threads"][0]["status"] == "open"
    assert all(row["reference"]["book"] <= 1 for row in first["facts"])
    assert all(row["id"] != pending_id for row in first["proposals"])
    assert first["links"][0]["from"] == ada and first["links"][0]["to"] == bex
    second = series_story_state.story_state(series_id, 2)
    assert any(row["scope"] == "reader_reveal" for row in second["facts"])
    assert any(thread["status"] == "resolved" for thread in second["threads"])
    assert pending_id in [row["id"] for row in second["proposals"]]
    assert pending_id not in [row["id"] for row in second["facts"]]


def test_approval_changes_projection_without_rewriting_source(universe):
    series_id, ada, bex, _, pending_id = universe
    with TestClient(app) as client:
        response = client.get(f"/api/series/{series_id}/story-state?book=2")
        assert response.status_code == 200
        assert pending_id not in [row["id"] for row in response.json()["facts"]]
        accepted = client.post(f"/api/series/{series_id}/assertions/{pending_id}/review",
                               json={"decision": "approved"})
        assert accepted.status_code == 200
        updated = client.get(f"/api/series/{series_id}/story-state?book=2")
        assert pending_id in [row["id"] for row in updated.json()["facts"]]
        assert updated.json()["links"][-1]["to"] == bex
        assert client.get(f"/api/series/{series_id}/story-state?book=99").status_code == 400


def test_belief_lens_is_not_world_canon(universe):
    series_id, ada, *_ = universe
    volumes = vault.series_detail(series_id)["volumes"]
    text = vault.source_text(series_id, volumes[0]["sources"][0]["id"])[1]
    phrase = "Ada fears the river."
    start = text.index(phrase)
    fact = canon.propose_fact(
        series_id, ada, "believes", object_text="the river is cursed",
        scope="character_belief", knower_id=ada, start_book=1,
        source_id=volumes[0]["sources"][0]["id"],
        quote_start=start, quote_end=start + len(phrase), quote=phrase,
    )
    canon.review_fact(series_id, fact["id"], "approved")
    first = series_story_state.story_state(series_id, 1)
    assert any(row["id"] == fact["id"] and row["scope"] == "character_belief"
               for row in first["facts"])
    assert not any(row["id"] == fact["id"] and row["scope"] == "world"
                   for row in first["facts"])

def test_modified_linked_manuscript_surfaces_stale_evidence_warning(universe):
    series_id, *_ = universe
    project = storage.create_project("Synthetic Linked Book")
    slug = project["slug"]
    original = storage.read_text(slug, "manuscript/chapter-001.md")
    vault.attach_project(series_id, slug, 3, title="Third Book", kind="novel",
                         edition_status="draft", rights_confirmed=True)
    assert not series_story_state.story_state(series_id, 3)["stale_sources"]
    storage.save_text(slug, "manuscript/chapter-001.md", original + " Changed source.")
    stale = series_story_state.story_state(series_id, 3)["stale_sources"]
    assert any(item["book"] == 3 and item["source_path"] == "manuscript/chapter-001.md"
               for item in stale)
