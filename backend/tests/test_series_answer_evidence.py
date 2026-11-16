"""Synthetic adversarial cases for the answer evidence screen."""
from app.series_answer_evidence import Evidence, classify


def test_tautology_and_missing_citation():
    result = classify("What does the Lantern Guild do?", "The Lantern Guild.")
    assert result.decision == "abstain"
    assert {"tautological_answer", "missing_evidence"} <= set(result.reasons)


def test_vague_summary_and_single_book_change():
    source = "Their friendship grew colder after the winter journey."
    result = classify("How did their relationship change over the series?",
                      "Worse than I expected.", [Evidence(source, source, 1)])
    assert result.decision == "abstain"
    assert {"vague_or_evasive_answer", "insufficient_temporal_evidence"} <= set(result.reasons)


def test_short_exact_match_is_not_support():
    result = classify("Who trained the messenger?", "Aster.",
                      [Evidence("Aster", "Aster never trained the messenger.", 1)])
    assert result.decision == "abstain"
    assert "short_quote" in result.reasons
    assert result.semantic_entailment == "unverified"


def test_exact_span_and_mismatch():
    source = "Before. The gardener taught Mira to read maps. After."
    quote = "The gardener taught Mira to read maps."
    result = classify("Who taught Mira?", "The gardener.", [Evidence(quote, source, 1, "s")])
    match = result.quote_matches[0]
    assert source[match.start:match.end] == quote
    assert match.source_id == "s"
    assert result.decision == "review"
    assert result.semantic_entailment == "unverified"
    invalid = classify("Who taught Mira?", "The gardener.", [Evidence(quote.lower(), source, 1)])
    assert invalid.decision == "abstain"
    assert "quote_not_found" in invalid.reasons
    assert not invalid.quote_matches


def test_membership_and_multiple_books_do_not_establish_entailment():
    first = "The gardener never taught Mira to read maps."
    second = "The gardener later returned to the old village."
    result = classify("How did their friendship change?", "They grew closer.",
                      [Evidence(first, first, 1), Evidence(second, second, 2)])
    assert result.decision == "review"
    assert result.semantic_entailment == "unverified"


def test_empty_quote_and_unknown_book():
    quote = "A sufficiently long quotation appears here."
    result = classify("How did it change over time?", "It became stronger.",
                      [Evidence("", "Any text", 1), Evidence(quote, quote)])
    assert result.decision == "abstain"
    assert {"quote_not_found", "insufficient_temporal_evidence"} <= set(result.reasons)
