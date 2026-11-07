"""Evidence-only Continuity Guardian, Consequence Map and professional Ember tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_consequences as consequences
from app import series_continuity as continuity
from app import series_ember, storage
from app import series_vault as vault
from app.main import app


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    series = vault.create_series("The Hollow Moon")
    passage1 = ("Kael hid the Moon Key in the glass vault. "
                "Mira believed the Moon Key was safe. "
                "The gate could only open beneath the winter stars.")
    passage2 = ("Kael moved the Moon Key into the old tower. "
                "Mira uncovered the secret and left for the coast.")
    one = vault.import_volume(series["id"], "book1.md", passage1.encode(), 1,
                              title="Winter Gate", kind="novel",
                              edition_status="published", rights_confirmed=True)
    two = vault.import_volume(series["id"], "book2.md", passage2.encode(), 2,
                              title="Summer Gate", kind="novel",
                              edition_status="published", rights_confirmed=True)
    moon = canon.add_entity(series["id"], "Moon Key", "artifact", aliases=["the key"])
    kael = canon.add_entity(series["id"], "Kael", "character")
    mira = canon.add_entity(series["id"], "Mira", "character")
    sources = [one["volumes"][0]["sources"][0], two["volumes"][1]["sources"][0]]
    for book, phrase, value, content in (
        (1, "Kael hid the Moon Key in the glass vault.", "glass vault", passage1),
        (2, "Kael moved the Moon Key into the old tower.", "old tower", passage2),
    ):
        start = content.index(phrase)
        proposed = canon.propose_fact(
            series["id"], moon["id"], "located_in", object_text=value,
            source_id=sources[book - 1]["id"], start_book=book,
            end_book=1 if book == 1 else None,
            quote_start=start, quote_end=start + len(phrase), quote=phrase,
        )
        canon.review_fact(series["id"], proposed["id"], "approved")
    return {"series": series["id"], "moon": moon["id"], "kael": kael["id"],
            "mira": mira["id"], "sources": sources,
            "text": (passage1, passage2)}


def test_scene_check_is_evidence_based_and_never_modifies_prose(world):
    series_id = world["series"]
    before = vault.source_text(series_id, world["sources"][1]["id"])[1]
    scene = "Kael opened the Moon Key's case. Moon Key is on the coast."
    result = continuity.scan_scene(
        series_id, scene=scene, book=2, assertions=[
            {"subject_id": world["moon"], "predicate": "located_in",
             "object_text": "coast", "scope": "world"},
        ],
    )
    assert result["read_only"] and not result["manuscript_modified"]
    assert len(result["findings"]) == 1
    assert result["findings"][0]["existing_values"] == ["old tower"]
    assert result["findings"][0]["evidence"][0]["quote"].startswith("Kael moved")
    assert result["mentions"]
    assert vault.source_text(series_id, world["sources"][1]["id"])[1] == before
    with pytest.raises(ValueError):
        continuity.scan_scene(series_id, scene=scene, book=2, assertions=[
            {"subject_id": "not-part-of-series", "predicate": "located_in",
             "object_text": "coast"},
        ])


def test_author_exception_persists_and_is_specific_to_scene_version(world):
    series_id = world["series"]
    claim = {"subject_id": world["moon"], "predicate": "located_in", "object_text": "sea"}
    first = continuity.scan_scene(series_id, scene="The Moon Key fell into the sea.",
                                  book=2, assertions=[claim])
    key = first["findings"][0]["claim_key"]
    saved = continuity.annotate_exception(
        series_id, key, "unreliable_narrator",
        "The witness believes the artifact is lost; the tower scene remains canon.")
    assert saved["reason"] == "unreliable_narrator"
    second = continuity.scan_scene(series_id, scene="The Moon Key fell into the sea.",
                                   book=2, assertions=[claim])
    assert second["findings"][0]["suppressed_by_author"]
    revised = continuity.scan_scene(series_id, scene="The Moon Key did not fall into the sea.",
                                    book=2, assertions=[claim])
    assert not revised["findings"][0]["suppressed_by_author"]
    assert continuity.clear_exception(series_id, key)["cleared"]
    assert not continuity.list_exceptions(series_id)


def test_consequence_map_tracks_active_history_and_later_citations(world):
    series_id = world["series"]
    view = consequences.preview_change(
        series_id, subject_id=world["moon"], predicate="located_in",
        proposed_value="inside the lighthouse", effective_book=2,
    )
    assert view["read_only"] and view["changes_applied"] == 0
    assert view["summary"]["direct_canon"] == 1
    assert view["direct"][0]["value"] == "old tower"
    assert view["direct"][0]["reference"]["book"] == 2
    assert any(row["source_path"] == "book2.md" for row in view["mentions"])
    assert all(item["book"] >= 2 for item in view["mentions"])
    note = consequences.save_change_note(
        series_id, proposal_id=view["proposal_id"],
        subject_id=world["moon"], predicate="located_in",
        proposed_value="inside the lighthouse", effective_book=2,
        scope="world", include_past=False,
        note="Consider retconning the artifact location after reviewing later mentions.")
    assert note["status"] == "open" and not note["canon_changed"]
    assert consequences.change_reviews(series_id)[0]["author_note"].startswith("Consider")
    assert consequences.dismiss_change(series_id, note["review_id"])["dismissed"]
    assert canon.at_book(series_id, 2)["facts"][0]["object_text"] == "old tower"


def test_consequence_map_includes_ongoing_earlier_rule(world):
    series_id = world["series"]
    rule = canon.add_entity(series_id, "Winter Gate", "rule")
    phrase = "The gate could only open beneath the winter stars."
    start = world["text"][0].index(phrase)
    asserted = canon.propose_fact(
        series_id, rule["id"], "opens_under",
        object_text="winter stars", start_book=1,
        source_id=world["sources"][0]["id"],
        quote_start=start, quote_end=start + len(phrase), quote=phrase,
    )
    canon.review_fact(series_id, asserted["id"], "approved")
    impact = consequences.preview_change(
        series_id, subject_id=rule["id"], predicate="opens_under",
        proposed_value="summer sun", effective_book=2,
    )
    assert impact["summary"]["direct_canon"] == 1


@pytest.mark.asyncio
async def test_professional_ember_keeps_scope_and_source_permissions(world, monkeypatch):
    series_id = world["series"]
    first = await series_ember.ask(series_id, "Where is the Moon Key?", book=1)
    assert "glass vault" in first["answer"]
    assert "old tower" not in first["answer"]
    assert first["read_only"] and not first["canon_changed"]
    second = await series_ember.ask(series_id, "Where is the Moon Key?", book=2)
    assert "old tower" in second["answer"]
    assert second["sources"][0]["book"] == 2
    calls = []

    async def fake_generate(config, messages, **kwargs):
        calls.append(messages)
        return "The Moon Key is in the old tower [SOURCE 1]."

    monkeypatch.setattr(series_ember, "generate", fake_generate)
    with pytest.raises(ValueError, match="Enable source sharing"):
        await series_ember.ask(series_id, "Where is the Moon Key?", book=2,
                              use_local_model=True, model="local:3b", allow_sources=False)
    assert not calls
    ai = await series_ember.ask(series_id, "Where is the Moon Key?", book=2,
                               use_local_model=True, model="local:3b", allow_sources=True)
    assert "[SOURCE 1]" in ai["answer"]
    assert len(calls) == 1
    assert "old tower" in calls[0][0]["content"]
    assert not ai["manuscripts_changed"]


def test_series_workflow_http_routes_are_read_only_until_approved(world):
    series_id = world["series"]
    with TestClient(app) as client:
        scan = client.post(f"/api/series/{series_id}/continuity/check", json={
            "scene": "The Moon Key is on the coast.", "book": 2,
            "assertions": [{"subject_id": world["moon"], "predicate": "located_in",
                            "object_text": "coast"}],
        })
        assert scan.status_code == 200, scan.text
        assert len(scan.json()["findings"]) == 1
        key = scan.json()["findings"][0]["claim_key"]
        ignored = client.post(
            f"/api/series/{series_id}/continuity/exceptions", json={
                "claim_key": key, "reason": "intentional_misdirection",
                "note": "This is a planned unreliable narrator moment.",
            })
        assert ignored.status_code == 201, ignored.text
        impact = client.post(f"/api/series/{series_id}/consequences/preview", json={
            "subject_id": world["moon"], "predicate": "located_in",
            "proposed_value": "the coast", "effective_book": 2,
        })
        assert impact.status_code == 200, impact.text
        assert impact.json()["changes_applied"] == 0
        ember = client.post(f"/api/series/{series_id}/ember/ask", json={
            "question": "Where is the Moon Key?", "book": 2,
        })
        assert ember.status_code == 200, ember.text
        assert "old tower" in ember.json()["answer"]
        assert ember.json()["actions"][0]["kind"] == "navigation_only"
