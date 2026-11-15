"""Adversarial synthetic metadata only; never evidence of author review."""
import copy
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("holdout", Path(__file__).resolve().parents[2] / "scripts/stage2_holdout.py")
holdout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(holdout)

feedback_spec = importlib.util.spec_from_file_location(
    "author_feedback", Path(__file__).resolve().parents[2] / "scripts/stage2_author_feedback.py"
)
feedback = importlib.util.module_from_spec(feedback_spec)
feedback_spec.loader.exec_module(feedback)


@pytest.fixture
def payload():
    source = {"id": "s", "edition": "first", "sha256": "a" * 64, "length": 50, "book": 1}
    citation = {"source_id": "s", "edition": "first", "source_sha256": "a" * 64,
                "start": 0, "end": 10, "reveal_at": [1, 1]}
    case = {"id": "q", "question": "Who knows?", "origin": "author_reviewed",
            "lens": "character_belief", "believer": "A", "as_of": [1, 2],
            "label": "answer", "answer": "A", "review_reference": "unverified",
            "review_status": "approved", "citations": [citation]}
    inventory = {"sources": [source], "cases": [case]}
    return {"inventory": inventory, "inventory_sha256": holdout.digest(inventory),
            "predictions": [{"id": "q", "label": "answer", "answer": "A"}]}


def test_honest_result(payload):
    result = holdout.evaluate(payload)
    assert result["accuracy"] == 1
    assert result["source_entailment"] is None
    assert not result["exact_match_semantics_verified"]
    assert not result["human_review_independently_verified"]
    assert not result["certified_5_of_5"]


def test_frozen_inventory(payload):
    payload["inventory"]["cases"][0]["answer"] = "B"
    with pytest.raises(ValueError, match="hash mismatch"):
        holdout.evaluate(payload)


@pytest.mark.parametrize("mutation", [
    lambda c: c.update(origin="synthetic"),
    lambda c: c.update(citations=[]),
    lambda c: c.update(review_reference=""),
    lambda c: c.update(review_status="pending"),
    lambda c: c.update(lens="truth"),
    lambda c: c.update(believer=""),
    lambda c: c.update(as_of=[1, 0]),
    lambda c: c["citations"][0].update(edition="other"),
    lambda c: c["citations"][0].update(source_sha256="b" * 64),
    lambda c: c["citations"][0].update(start=True),
    lambda c: c["citations"][0].update(end=51),
    lambda c: c["citations"][0].update(reveal_at=[1, 3]),
    lambda c: c.update(label="abstain"),
])
def test_rejects_invalid_cases(payload, mutation):
    mutation(payload["inventory"]["cases"][0])
    payload["inventory_sha256"] = holdout.digest(payload["inventory"])
    with pytest.raises(ValueError):
        holdout.evaluate(payload)


def test_fifty_duplicate_questions_rejected(payload):
    cases = payload["inventory"]["cases"]
    for i in range(49):
        case = copy.deepcopy(cases[0])
        case["id"] = str(i)
        cases.append(case)
    payload["inventory_sha256"] = holdout.digest(payload["inventory"])
    with pytest.raises(ValueError, match="duplicate question"):
        holdout.evaluate(payload)


def test_abstention_and_missing_prediction(payload):
    case = payload["inventory"]["cases"][0]
    case.update(label="abstain", answer=None)
    payload["inventory_sha256"] = holdout.digest(payload["inventory"])
    payload["predictions"][0].update(label="abstain", answer=None)
    result = holdout.evaluate(payload)
    assert result["correct_abstentions"] == 1
    assert result["abstention_rate"] == 1
    payload["predictions"] = []
    with pytest.raises(ValueError, match="cover"):
        holdout.evaluate(payload)


def test_local_source_bytes_and_citation_match(payload, tmp_path):
    data = b"synthetic source bytes"
    source = payload["inventory"]["sources"][0]
    citation = payload["inventory"]["cases"][0]["citations"][0]
    source.update(sha256=holdout.hashlib.sha256(data).hexdigest(), length=len(data))
    citation.update(source_sha256=source["sha256"], span_sha256=holdout.hashlib.sha256(data[:10]).hexdigest())
    source_file = tmp_path / "private.txt"
    source_file.write_bytes(data)
    payload["source_paths"] = {"s": str(source_file)}
    payload["inventory_sha256"] = holdout.digest(payload["inventory"])
    payload["predictions"][0]["citations"] = [{"source_id": "s", "start": 0, "end": 10}]
    result = holdout.evaluate(payload)
    assert result["source_bytes_verified"] and result["citation_matches"] == 1
    payload["predictions"][0]["citations"][0]["end"] = 9
    assert holdout.evaluate(payload)["citation_matches"] == 0
    source_file.write_bytes(b"x" * len(data))
    with pytest.raises(ValueError, match="source bytes mismatch"):
        holdout.evaluate(payload)


def test_span_hash_and_duplicate_provenance_rejected(payload, tmp_path):
    data = b"x" * 50
    source = payload["inventory"]["sources"][0]
    citation = payload["inventory"]["cases"][0]["citations"][0]
    source["sha256"] = holdout.hashlib.sha256(data).hexdigest()
    citation.update(source_sha256=source["sha256"], span_sha256="0" * 64)
    source_file = tmp_path / "source"
    source_file.write_bytes(data)
    payload["source_paths"] = {"s": str(source_file)}
    payload["inventory_sha256"] = holdout.digest(payload["inventory"])
    with pytest.raises(ValueError, match="span hash mismatch"):
        holdout.evaluate(payload)
    duplicate = copy.deepcopy(source)
    duplicate["id"] = "alias"
    payload["inventory"]["sources"].append(duplicate)
    payload["inventory_sha256"] = holdout.digest(payload["inventory"])
    with pytest.raises(ValueError, match="duplicate source provenance"):
        holdout.evaluate(payload)


def test_similar_questions_are_flagged_not_certified(payload):
    other = copy.deepcopy(payload["inventory"]["cases"][0])
    other.update(id="other", question="Who knows now?")
    payload["inventory"]["cases"].append(other)
    payload["predictions"].append({"id": "other", "label": "answer", "answer": "A"})
    payload["inventory_sha256"] = holdout.digest(payload["inventory"])
    assert not holdout.evaluate(payload)["semantic_distinctness_verified"]


@pytest.fixture
def feedback_payload():
    outputs = [{"id": f"item-{i}", "output_sha256": str(i) * 64} for i in range(5)]
    run = {"kind": "local_diagnostic_top_hit", "model_sha256": "a" * 64,
           "configuration_sha256": "b" * 64, "source_provenance": "synthetic",
           "outputs": outputs}
    run_hash = feedback.digest(run)
    items = [{**output, "verdict": verdict} for output, verdict in zip(
        outputs, ["unknown", "unreviewed", "incorrect", "partly_correct", "correct"],
        strict=True)]
    return {"run": run, "run_sha256": run_hash,
            "reviews": [{"run_sha256": run_hash, "reviewer": "author", "items": items}]}


def test_author_feedback_denominator_and_partial_credit(feedback_payload):
    result = feedback.evaluate(feedback_payload)
    assert result["reviewed_denominator"] == 3
    assert result["credit_points"] == 1.5
    assert result["credit_rate"] == 0.5
    assert result["counts"]["unknown"] == result["counts"]["unreviewed"] == 1
    assert not result["production_evaluation"]
    assert not result["independent_review_verified"]


def test_author_feedback_merge_and_empty_denominator(feedback_payload):
    batch = feedback_payload["reviews"][0]
    second = {**batch, "items": batch["items"][2:]}
    batch["items"] = batch["items"][:2]
    feedback_payload["reviews"].append(second)
    assert feedback.evaluate(feedback_payload)["reviewed_denominator"] == 3
    for review in feedback_payload["reviews"]:
        for item in review["items"]:
            item["verdict"] = "unreviewed"
    assert feedback.evaluate(feedback_payload)["credit_rate"] is None


@pytest.mark.parametrize("mutation", [
    lambda p: p["reviews"][0]["items"].pop(),
    lambda p: p["reviews"][0]["items"].append(copy.deepcopy(p["reviews"][0]["items"][0])),
    lambda p: p["reviews"][0]["items"][0].update(id="extra"),
    lambda p: p["reviews"][0]["items"][0].update(output_sha256="f" * 64),
    lambda p: p["reviews"][0]["items"][0].update(verdict="approved"),
    lambda p: p["reviews"][0].update(reviewer="expert"),
    lambda p: p["reviews"][0].update(run_sha256="f" * 64),
    lambda p: p["run"].update(kind="production"),
    lambda p: p["run"]["outputs"].append(copy.deepcopy(p["run"]["outputs"][0])),
    lambda p: p["reviews"][0]["items"][0].update(excerpt="private"),
])
def test_author_feedback_rejects_invalid_inputs(feedback_payload, mutation):
    mutation(feedback_payload)
    with pytest.raises((ValueError, TypeError)):
        feedback.evaluate(feedback_payload)
