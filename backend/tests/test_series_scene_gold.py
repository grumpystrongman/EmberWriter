"""Predeclared literary gold: reproducible, local and never self-certifying."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import series_scene_gold as gold
from app import series_scene_reviews as reviews
from app import series_scene_windows as windows
from app import series_vault as vault
from app import storage
from app.main import app


@pytest.fixture
def book(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,"PROJECTS_ROOT",tmp_path/"projects")
    sid=vault.create_series("Literary Gold Fixture")["id"]
    text="Mira watched the harbor.\n\n"+"The light faded. " * 460
    record=vault.import_volume(
        sid,"book.md",text.encode(),1,title="Synthetic Book One",
        kind="novel",edition_status="reference",rights_confirmed=True,
    )
    return sid,record["volumes"][0]["sources"][0]["id"]


def test_fixture_bank_has_independent_gold_and_adversarial_categories():
    assert len(gold.GOLD)==gold.EXPECTED_FIXTURE_COUNT
    cases=[gold._case(row) for row in gold.GOLD]
    assert len({case["id"] for case in cases})==len(cases)
    assert sum(case["gold_break"] for case in cases)>=6
    assert sum(not case["gold_break"] for case in cases)>=4
    assert any("dream" in case["id"] for case in cases)
    assert any("belief" in case["id"] for case in cases)
    assert any(len(case["text"])>windows.WINDOW_LIMIT for case in cases)
    for case in cases:
        assert case["text"]
        assert 0<case["gold_at"]<len(case["text"])
        assert case["gold_pov"] in {
            "first_person","third_limited","third_omniscient",
        }


def test_scene_navigation_does_not_pass_as_semantic_certification():
    result=gold.score_boundary_candidates()
    assert result["case_count"]==12
    assert len(result["fixture_sha256"])==64
    assert result["fixture_sha256"]==gold.score_boundary_candidates()["fixture_sha256"]
    assert result["scene_interpretation_gate"]=="blocked"
    assert not result["automatic_scene_approval_allowed"]
    assert not result["external_model_calls"] and not result["source_text_sent"]
    assert result["pov"]["prediction_coverage"]==1
    assert result["character_knowledge"]["prediction_coverage"]==0
    assert result["boundary"]["false_positive"]==0
    assert result["boundary"]["false_negative"]>=1
    assert result["boundary"]["f1"]<0.90
    assert result["boundary"]["true_positive"]>=2
    assert any(x["boundary_result"]=="miss" for x in result["cases"])
    assert any(x["boundary_result"]=="correct_rejection" for x in result["cases"])
    assert sum(x["predicted_pov"]!="undetermined" for x in result["cases"])==1
    assert all(x["predicted_character_knowledge"]=="unknown" for x in result["cases"])


def test_even_a_perfect_simple_case_cannot_self_certify_semantics():
    result=gold.score_boundary_candidates((gold._case(gold.GOLD[0]),))
    assert result["boundary"]["f1"]==1.0
    assert result["scene_interpretation_gate"]=="blocked"
    assert result["pov"]["prediction_coverage"]==0
    assert not result["automatic_scene_approval_allowed"]


def test_scoring_counts_every_extra_candidate_as_false_positive():
    case=gold._case(gold.GOLD[-1])
    assert not case["gold_break"]
    outcome=gold.score_boundary_candidates((case,))
    assert outcome["boundary"]["false_positive"]==0
    assert outcome["boundary"]["true_positive"]==0


def test_evaluation_route_is_read_only_and_isolated(book):
    sid,_source_id=book
    second=vault.create_series("Different Fiction")["id"]
    with TestClient(app) as client:
        target=f"/api/series/{sid}/scene-evaluation"
        response=client.get(target,params={"book":1})
        assert response.status_code==200,response.text
        value=response.json()
        assert value["case_count"]==12
        assert value["author_reviews"]["shown"]==0
        assert value["author_reviews"]["cannot_be_used_as_gold_automatically"]
        assert value["scene_interpretation_gate"]=="blocked"
        assert not value["external_model_calls"]
        assert client.get(target,params={"book":0}).status_code==422
        assert client.get(f"/api/series/{second}/scene-evaluation",params={"book":1}).json()["author_reviews"]["shown"]==0
        assert client.get(f"/api/series/{'f'*32}/scene-evaluation").status_code==404
        assert reviews.list_reviews(sid)==[]
        assert len(vault.series_detail(sid)["volumes"][0]["sources"])==1


def test_evaluation_counts_author_review_but_never_promotes_to_gold(book):
    sid,source=book
    window=windows.scan(sid,book=1)["windows"][0]
    staged=reviews.stage(sid,source_id=source,book=1,start=window["start"],end=window["end"])
    report=gold.evaluate(sid,book=1)
    assert report["author_reviews"]["shown"]==1
    assert report["author_reviews"]["pending"]==1
    assert report["author_reviews"]["author_confirmed_scenes"]==0
    assert report["scene_interpretation_gate"]=="blocked"
    reviews.decide(sid,staged["id"],decision="approved",
                   title="Mira watches the harbor",kind="actual_scene")
    new=gold.evaluate(sid,book=1)
    assert new["author_reviews"]["author_confirmed_scenes"]==1
    assert new["case_count"]==12
    assert new["pov"]["prediction_coverage"]==1
    assert new["scene_interpretation_gate"]=="blocked"


def test_one_to_one_matching_penalizes_near_duplicate_candidate(monkeypatch):
    case = gold._case(gold.GOLD[0])
    at = case["gold_at"]
    # Two starts fall within the matching tolerance of one real boundary.
    # A scoring implementation must not award both as true positives.
    monkeypatch.setattr(
        windows, "scene_suggestions",
        lambda content: [{"offset": at}, {"offset": at + 1}],
    )
    result = gold.score_boundary_candidates((case,))
    assert result["boundary"]["true_positive"] == 1
    assert result["boundary"]["false_positive"] == 1
    assert result["cases"][0]["extraneous_breaks"] == 1
    assert result["boundary"]["precision"] == 0.5
    assert result["scene_interpretation_gate"] == "blocked"


@pytest.mark.parametrize("change", [
    {"id": ""},
    {"gold_at": 0},
    {"gold_at": True},
    {"gold_at": 999999},
    {"gold_break": 1},
    {"gold_pov": "invented"},
    {"gold_knowledge": "certainly"},
    {"text": ""},
])
def test_malformed_gold_fails_closed(change):
    case = gold._case(gold.GOLD[0])
    case.update(change)
    with pytest.raises(ValueError):
        gold.score_boundary_candidates((case,))


def test_duplicate_gold_ids_fail_closed():
    case = gold._case(gold.GOLD[0])
    with pytest.raises(ValueError, match="unique"):
        gold.score_boundary_candidates((case, dict(case)))


def test_one_boundary_cannot_cancel_extra_long_window_splits(monkeypatch):
    case = gold._case(gold.GOLD[0])
    at = case["gold_at"]
    # Keep a real match and add one distant convenience split.
    monkeypatch.setattr(
        windows, "scene_suggestions",
        lambda content: [{"offset": at // 2}, {"offset": at}],
    )
    result = gold.score_boundary_candidates((case,))
    assert result["boundary"]["true_positive"] == 1
    assert result["boundary"]["false_positive"] == 1
    assert result["cases"][0]["matched_candidate_start"] == at
