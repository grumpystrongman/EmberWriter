"""Offline, fail-closed scoring of a separately labeled Stage 2 holdout.

Inputs are private JSON on stdin. Optional local byte verification checks hashes, not human identity,
semantic distinctness, source entailment, or freeze timing.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HASH = re.compile(r"^[0-9a-f]{64}$")
LENSES = {"world_truth", "character_belief", "reader_revelation"}
LABELS = {"answer", "abstain"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def text(value):
    return isinstance(value, str) and bool(value.strip())


def position(value):
    return (isinstance(value, list) and len(value) == 2 and
            all(type(n) is int and n > 0 for n in value))


def verify_source_bytes(sources, cases, paths):
    """Check byte hashes and half-open spans locally; never return source content."""
    if not isinstance(paths, dict) or set(paths) != {s["id"] for s in sources}:
        raise ValueError("source path mapping must cover sources exactly")
    for source in sources:
        path = paths[source["id"]]
        if not isinstance(path, str) or not path:
            raise ValueError("invalid source path")
        try:
            data = Path(path).read_bytes()
        except (OSError, ValueError):
            raise ValueError("source file unavailable") from None
        if len(data) != source["length"] or hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError("source bytes mismatch")
        for case in cases:
            for citation in case["citations"]:
                if citation["source_id"] == source["id"]:
                    span_hash = citation.get("span_sha256")
                    if not isinstance(span_hash, str) or not HASH.fullmatch(span_hash):
                        raise ValueError("citation span hash required for byte verification")
                    if hashlib.sha256(data[citation["start"]:citation["end"]]).hexdigest() != span_hash:
                        raise ValueError("citation span hash mismatch")


def evaluate(payload):
    """Validate a frozen inventory and score blind predictions against its labels."""
    if not isinstance(payload, dict):
        raise ValueError("expected object")
    inventory = payload.get("inventory")
    predictions = payload.get("predictions")
    if not isinstance(inventory, dict) or not isinstance(predictions, list):
        raise ValueError("inventory and predictions required")
    if not HASH.fullmatch(str(payload.get("inventory_sha256", ""))) or digest(inventory) != payload["inventory_sha256"]:
        raise ValueError("inventory hash mismatch")
    sources = inventory.get("sources")
    cases = inventory.get("cases")
    if not isinstance(sources, list) or not sources or not isinstance(cases, list) or not cases:
        raise ValueError("sources and cases required")
    source_map = {}
    for source in sources:
        if not isinstance(source, dict) or not text(source.get("id")) or source["id"] in source_map:
            raise ValueError("invalid source id")
        if not text(source.get("edition")) or not HASH.fullmatch(str(source.get("sha256", ""))):
            raise ValueError("invalid source edition or hash")
        if type(source.get("length")) is not int or source["length"] < 1 or type(source.get("book")) is not int or source["book"] < 1:
            raise ValueError("invalid source length or book")
        source_map[source["id"]] = source
    if len({(s["sha256"], s["book"]) for s in sources}) != len(sources):
        raise ValueError("duplicate source provenance")
    case_map = {}
    questions = set()
    for case in cases:
        if not isinstance(case, dict) or not text(case.get("id")) or case["id"] in case_map:
            raise ValueError("invalid case id")
        question = case.get("question")
        if not text(question):
            raise ValueError("invalid question")
        normalized = re.sub(r"\W+", " ", question.casefold()).strip()
        if not normalized or normalized in questions:
            raise ValueError("duplicate question")
        questions.add(normalized)
        if case.get("origin") != "author_reviewed" or case.get("lens") not in LENSES:
            raise ValueError("invalid origin or lens")
        if case.get("lens") == "character_belief" and not text(case.get("believer")):
            raise ValueError("belief requires believer")
        if not position(case.get("as_of")) or case.get("label") not in LABELS:
            raise ValueError("invalid cutoff or label")
        if case["label"] == "answer" and not text(case.get("answer")):
            raise ValueError("answer required")
        if case["label"] == "abstain" and case.get("answer") is not None:
            raise ValueError("abstention cannot have answer")
        if not text(case.get("review_reference")) or case.get("review_status") != "approved":
            raise ValueError("review attestation required")
        citations = case.get("citations")
        if not isinstance(citations, list) or not citations:
            raise ValueError("citations required, including negative cases")
        for citation in citations:
            if not isinstance(citation, dict) or citation.get("source_id") not in source_map:
                raise ValueError("invalid citation source")
            source = source_map[citation["source_id"]]
            if citation.get("edition") != source["edition"] or citation.get("source_sha256") != source["sha256"]:
                raise ValueError("citation edition or hash mismatch")
            start, end = citation.get("start"), citation.get("end")
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= source["length"]:
                raise ValueError("invalid citation coordinates")
            if not position(citation.get("reveal_at")) or citation["reveal_at"][0] != source["book"] or citation["reveal_at"] > case["as_of"]:
                raise ValueError("citation outside cutoff")
        case_map[case["id"]] = case
    paths = payload.get("source_paths")
    if paths is not None:
        verify_source_bytes(sources, cases, paths)
    observed = {}
    for prediction in predictions:
        if not isinstance(prediction, dict) or prediction.get("id") not in case_map or prediction["id"] in observed:
            raise ValueError("invalid prediction id")
        if prediction.get("label") not in LABELS:
            raise ValueError("invalid prediction label")
        if prediction["label"] == "answer" and not text(prediction.get("answer")):
            raise ValueError("prediction answer required")
        if prediction["label"] == "abstain" and prediction.get("answer") is not None:
            raise ValueError("invalid abstention")
        cited = prediction.get("citations")
        if cited is not None:
            if not isinstance(cited, list) or any(
                not isinstance(c, dict) or set(c) != {"source_id", "start", "end"}
                or not isinstance(c["source_id"], str)
                or type(c["start"]) is not int or type(c["end"]) is not int
                for c in cited
            ):
                raise ValueError("invalid prediction citations")
        observed[prediction["id"]] = prediction
    if set(observed) != set(case_map):
        raise ValueError("predictions must cover holdout exactly")
    correct = sum(p["label"] == c["label"] and (c["label"] == "abstain" or p["answer"].strip().casefold() == c["answer"].strip().casefold()) for i, c in case_map.items() for p in [observed[i]])
    abstained = sum(p["label"] == "abstain" for p in observed.values())
    negatives = sum(c["label"] == "abstain" for c in cases)
    correct_abstentions = sum(c["label"] == "abstain" and observed[i]["label"] == "abstain" for i, c in case_map.items())
    # A triage signal only: paraphrases with different vocabulary remain undetected.
    token_sets = [set(re.findall(r"\w+", c["question"].casefold())) for c in cases]
    similar_pairs = sum(
        len(a & b) / len(a | b) >= 0.8
        for i, a in enumerate(token_sets) for b in token_sets[i + 1:]
        if a | b
    )
    citation_matches = 0
    for case_id, case in case_map.items():
        prediction = observed[case_id]
        allowed = {(c["source_id"], c["start"], c["end"]) for c in case["citations"]}
        cited = prediction.get("citations")
        if (case["label"] == "answer" and prediction["label"] == "answer"
                and cited and all((c["source_id"], c["start"], c["end"]) in allowed for c in cited)):
            citation_matches += 1
    return {"inventory_sha256": digest(inventory), "total": len(cases), "correct": correct,
            "accuracy": correct / len(cases), "abstention_rate": abstained / len(cases),
            "negative_cases": negatives, "correct_abstentions": correct_abstentions,
            "citation_matches": citation_matches, "similar_question_pairs": similar_pairs,
            "source_entailment": None, "source_bytes_verified": paths is not None,
            "human_review_independently_verified": False, "semantic_distinctness_verified": False,
            "certified_5_of_5": False}


def main():
    if len(sys.argv) != 1:
        raise SystemExit("Pipe private JSON through stdin; no paths accepted")
    try:
        result = evaluate(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError, OSError):
        raise SystemExit("Invalid input or verification failed; inspect locally without logging private data") from None
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
