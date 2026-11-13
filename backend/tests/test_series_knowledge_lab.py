"""Evidence-led 80-book-compatible knowledge lab acceptance.

Synthetic prose only: never copies the user's private Destroyer books.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import series_canon as canon
from app import series_knowledge_lab as lab
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def cycle(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(storage, "PROJECTS_ROOT", tmp_path / "projects")
    series_id = vault.create_series("The Glass Horizon")["id"]
    texts = [
        "Mira mistrusted Rowan after the bridge fell. The blue crown rested in the crypt. The crown foreshadows the sealed gate.",
        "Rowan showed Mira the ledger. Mira learned Rowan had defended her. The blue crown traveled to the tower.",
        "Mira told Rowan about the crown. They chose to protect each other. The crown resolves the sealed gate mystery.",
    ]
    sources = []
    for ordinal, text in enumerate(texts, 1):
        vault.import_volume(series_id, f"book-{ordinal}.md", text.encode(), ordinal,
                            title=f"Book {ordinal}", kind="novel",
                            edition_status="reference", rights_confirmed=True)
        sources.append(vault.series_detail(series_id)["volumes"][-1]["sources"][0]["id"])
    mira = canon.add_entity(series_id, "Mira", "character")
    rowan = canon.add_entity(series_id, "Rowan", "character")
    crown = canon.add_entity(series_id, "Blue Crown", "artifact")
    return series_id, texts, sources, mira, rowan, crown


def claim(cycle, book, phrase, subject, predicate, value, *,
          scope="world", knower=None, target=None,
          sequence=0, end_book=None):
    sid, texts, sources, *_ = cycle
    idx = texts[book-1].index(phrase)
    return canon.propose_fact(
        sid, subject["id"], predicate, object_text=value,
        object_entity_id=target["id"] if target else None,
        scope=scope, knower_id=knower["id"] if knower else None,
        start_book=book, start_sequence=sequence, end_book=end_book,
        source_id=sources[book-1], quote_start=idx, quote_end=idx+len(phrase),
        quote=phrase,
    )


def test_approved_only_and_book_cutoff_do_not_leak(cycle):
    sid, _, _, _mira, _rowan, crown = cycle
    old = claim(cycle, 1, "crown rested in the crypt", crown,
                "located_in", "crypt", end_book=1)
    new = claim(cycle, 2, "crown traveled to the tower", crown,
                "located_in", "tower")
    assert lab.investigate(sid, 1, subject_id=crown["id"])["answer_status"] == "insufficient_approved_evidence"
    canon.review_fact(sid, old["id"], "approved")
    canon.review_fact(sid, new["id"], "approved")
    first = lab.investigate(sid, 1, subject_id=crown["id"])
    assert [f["value"] for f in first["world_truths"]] == ["crypt"]
    assert "tower" not in str(first)
    second = lab.investigate(sid, 2, subject_id=crown["id"])
    assert [f["value"] for f in second["world_truths"]] == ["tower"]
    assert len(second["recorded_changes"]) == 1
    assert second["recorded_changes"][0]["classification"] == "recorded_change"
    assert not second["possible_conflicts"]


def test_beliefs_reader_secrets_are_independently_scoped(cycle):
    sid, _, _, mira, rowan, _crown = cycle
    belief = claim(cycle, 1, "Mira mistrusted Rowan", rowan,
                   "trust", "untrustworthy", knower=mira, scope="character_belief",
                   target=mira)
    reveal = claim(cycle, 2, "Mira learned Rowan had defended her",
                   rowan, "defended", "protected Mira", scope="reader_reveal")
    canon.review_fact(sid, belief["id"], "approved")
    canon.review_fact(sid, reveal["id"], "approved")
    b1 = lab.investigate(sid, 1, knower_id=mira["id"])
    assert len(b1["character_beliefs"]) == 1
    assert b1["reader_reveals"] == []
    b2 = lab.investigate(sid, 2, knower_id=mira["id"])
    assert len(b2["reader_reveals"]) == 1
    assert b2["world_truths"] == []
    assert not b1["possible_conflicts"]


def test_exclusive_overlaps_flagged_but_relationships_not_equated(cycle):
    sid, _, _, _mira, _rowan, crown = cycle
    first = claim(cycle, 1, "crown rested in the crypt", crown,
                  "located_in", "crypt")
    second = claim(cycle, 2, "crown traveled to the tower", crown,
                   "located_in", "tower")
    for item in [first, second]:
        canon.review_fact(sid, item["id"], "approved")
    b2 = lab.investigate(sid, 2, subject_id=crown["id"])
    assert len(b2["possible_conflicts"]) == 1
    assert b2["possible_conflicts"][0]["requires_author_review"] is True
    assert {row["value"] for row in b2["world_truths"]} == {"crypt", "tower"}


def test_future_book_and_future_scene_not_visible(cycle):
    sid, _, _, mira, rowan, _crown = cycle
    future = claim(cycle, 3, "Mira told Rowan", mira,
                   "trusts", "Rowan", target=rowan, sequence=3)
    canon.review_fact(sid, future["id"], "approved")
    assert not lab.investigate(sid, 2)["relationships"]
    assert not lab.investigate(sid, 3, sequence=2)["relationships"]
    assert len(lab.investigate(sid, 3, sequence=3)["relationships"]) == 1


def test_zero_approved_facts_abstains_and_project_stays_unchanged(cycle):
    sid, _, _, mira, rowan, _crown = cycle
    candidate = claim(cycle, 1, "Mira mistrusted Rowan", mira,
                      "distrusts", "Rowan", target=rowan)
    payload = lab.investigate(sid, 3, subject_id=mira["id"])
    assert payload["approved_evidence_count"] == 0
    assert payload["answer_status"] == "insufficient_approved_evidence"
    assert payload["pending_proposals_visible"] == 1
    assert payload["model_called"] is False
    assert canon.fact(sid, candidate["id"])["status"] == "proposed"


def test_endpoints_cannot_mix_entities_between_series(cycle):
    sid, _, _, mira, _rowan, _crown = cycle
    alien = vault.create_series("Unrelated private world")["id"]
    alien_mira = canon.add_entity(alien, "Mira", "character")
    with TestClient(app) as client:
        path = f"/api/series/{sid}/knowledge-lab"
        valid = client.get(path, params={"book": 1, "subject_id": mira["id"]})
        assert valid.status_code == 200
        assert valid.json()["evidence_only"]
        cross = client.get(path, params={"book": 1, "subject_id": alien_mira["id"]})
        assert cross.status_code == 404
        invalid = client.get(path, params={"book": 99})
        assert invalid.status_code in (400, 404, 422)


def test_causal_thread_setup_and_payoff_are_source_bound_and_not_spoiled(cycle):
    sid, _, _, _mira, _rowan, crown = cycle
    setup = claim(cycle, 1, "The crown foreshadows the sealed gate",
                  crown, "foreshadows", "sealed gate")
    payoff = claim(cycle, 3, "The crown resolves the sealed gate mystery",
                   crown, "resolves", "sealed gate mystery")
    canon.review_fact(sid, setup["id"], "approved")
    canon.review_fact(sid, payoff["id"], "approved")
    first = lab.investigate(sid, 1, subject_id=crown["id"])
    assert len(first["causal_links"]) == 1
    assert len(first["thread_lifecycle"]) == 1
    assert first["thread_lifecycle"][0]["status"] == "open"
    assert first["thread_lifecycle"][0]["payoffs"] == []
    assert "mystery" not in str(first)
    last = lab.investigate(sid, 3, subject_id=crown["id"])
    assert last["thread_lifecycle"][0]["status"] == "resolved"
    assert len(last["thread_lifecycle"][0]["payoffs"]) == 1
    assert all(item["citation"]["source_id"]
               for item in last["thread_lifecycle"][0]["evidence"])


def test_multiple_nonexclusive_character_goals_are_not_a_conflict(cycle):
    sid, _, _, mira, _rowan, _crown = cycle
    first = claim(cycle, 1, "Mira mistrusted Rowan", mira, "wants", "safety")
    second = claim(cycle, 2, "Mira learned Rowan had defended her",
                   mira, "wants", "understanding")
    canon.review_fact(sid, first["id"], "approved")
    canon.review_fact(sid, second["id"], "approved")
    result = lab.investigate(sid, 2, subject_id=mira["id"])
    assert result["possible_conflicts"] == []
    assert result["recorded_changes"][0]["classification"] == "coexisting_claims"
    assert canon.at_book(sid, 2)["conflicts"] == []


def test_two_character_filter_requires_actual_shared_evidence(cycle):
    sid, _, _, mira, rowan, _crown = cycle
    shared = claim(cycle, 3, "Mira told Rowan", mira,
                   "trusts", "Rowan", target=rowan)
    unrelated = claim(cycle, 1, "Mira mistrusted Rowan", mira,
                      "fears", "being alone")
    separate = claim(cycle, 2, "Rowan showed Mira the ledger", rowan,
                     "wants", "the ledger")
    for row in (shared, unrelated, separate):
        canon.review_fact(sid, row["id"], "approved")
    state = lab.investigate(sid, 3, subject_id=mira["id"],
                            other_id=rowan["id"])
    assert [row["id"] for row in state["history"]] == [shared["id"]]
    assert [row["id"] for row in state["relationships"]] == [shared["id"]]
    assert state["possible_conflicts"] == []
