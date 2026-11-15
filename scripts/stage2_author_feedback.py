"""Aggregate author judgments of one local diagnostic run, without source text."""

import hashlib
import json
import re
import sys

HASH = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
VERDICTS = {"correct", "partly_correct", "incorrect", "unknown", "unreviewed"}


def digest(value):
    """Hash canonical JSON; this is an integrity fingerprint, not an attestation."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("unexpected or missing fields")


def fingerprint(value):
    return isinstance(value, str) and HASH.fullmatch(value) is not None


def evaluate(payload):
    """Merge review batches by ID and fingerprint; require explicit coverage."""
    fields(payload, {"run", "run_sha256", "reviews"})
    run = payload["run"]
    fields(run, {"kind", "model_sha256", "configuration_sha256", "source_provenance",
                 "outputs"})
    if run["kind"] != "local_diagnostic_top_hit":
        raise ValueError("unsupported run kind")
    if not fingerprint(run["model_sha256"]) or not fingerprint(run["configuration_sha256"]):
        raise ValueError("invalid run fingerprint")
    if run["source_provenance"] not in {"local_corpus", "synthetic", "unknown"}:
        raise ValueError("invalid source provenance")
    outputs = run["outputs"]
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("outputs required")
    expected = {}
    for output in outputs:
        fields(output, {"id", "output_sha256"})
        item_id = output["id"]
        if not isinstance(item_id, str) or not ID.fullmatch(item_id) or item_id in expected:
            raise ValueError("invalid or duplicate output id")
        if not fingerprint(output["output_sha256"]):
            raise ValueError("invalid output fingerprint")
        expected[item_id] = output["output_sha256"]
    if not fingerprint(payload["run_sha256"]) or payload["run_sha256"] != digest(run):
        raise ValueError("run fingerprint mismatch")
    reviews = payload["reviews"]
    if not isinstance(reviews, list) or not reviews:
        raise ValueError("reviews required")
    merged = {}
    for batch in reviews:
        fields(batch, {"run_sha256", "reviewer", "items"})
        if batch["run_sha256"] != payload["run_sha256"] or batch["reviewer"] != "author":
            raise ValueError("review provenance mismatch")
        if not isinstance(batch["items"], list) or not batch["items"]:
            raise ValueError("review items required")
        for item in batch["items"]:
            fields(item, {"id", "output_sha256", "verdict"})
            item_id = item["id"]
            if not isinstance(item_id, str) or item_id not in expected or item_id in merged:
                raise ValueError("invalid or duplicate review id")
            if item["output_sha256"] != expected[item_id] or item["verdict"] not in VERDICTS:
                raise ValueError("review output or verdict mismatch")
            merged[item_id] = item["verdict"]
    if set(merged) != set(expected):
        raise ValueError("reviews must cover every output explicitly")
    counts = {label: list(merged.values()).count(label) for label in sorted(VERDICTS)}
    reviewed = counts["correct"] + counts["partly_correct"] + counts["incorrect"]
    # One half is a declared reporting convention, not a claim about semantic quality.
    credit = counts["correct"] + 0.5 * counts["partly_correct"]
    return {"run_sha256": payload["run_sha256"], "run_kind": run["kind"],
            "source_provenance": run["source_provenance"], "total_outputs": len(expected),
            "counts": counts, "reviewed_denominator": reviewed,
            "partial_credit_weight": 0.5, "credit_points": credit,
            "credit_rate": credit / reviewed if reviewed else None,
            "production_evaluation": False, "independent_review_verified": False,
            "semantic_validation_verified": False}


def main():
    if len(sys.argv) != 1:
        raise SystemExit("Pipe JSON through stdin; no paths accepted")
    try:
        result = evaluate(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError):
        raise SystemExit("Invalid input or verification failed; inspect locally") from None
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
