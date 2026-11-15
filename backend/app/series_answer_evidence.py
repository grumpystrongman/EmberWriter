"""Conservative, local screening; quotation membership is not entailment."""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    quote: str
    source_text: str
    book: str | int | None = None
    source_id: str | None = None


@dataclass(frozen=True)
class QuoteMatch:
    source_id: str | None
    book: str | int | None
    start: int
    end: int


@dataclass(frozen=True)
class Assessment:
    decision: str
    reasons: tuple[str, ...]
    quote_matches: tuple[QuoteMatch, ...]
    semantic_entailment: str = "unverified"


def _words(text: str) -> list[str]:
    return re.findall(r"[^\W_]+(?:['’][^\W_]+)?", text.casefold())


_STOP = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did",
    "what", "how", "why", "who", "whom", "whose", "of", "to", "in", "on",
    "for", "with", "and", "or", "that", "this", "it", "its", "their",
    "they", "he", "she",
})
_CHANGE = re.compile(
    r"\b(?:changed|change|evolved|grew|growth|developed|development|became|become|"
    r"improved|worsened|closer|further|more|less|earlier|later|over time|"
    r"across (?:the )?(?:books|series)|throughout (?:the )?(?:books|series)|"
    r"from .+? to)\b", re.IGNORECASE,
)
_VAGUE = re.compile(
    r"\b(?:it(?:'s| is) complicated|hard to say|who knows|"
    r"(?:worse|better) than (?:i|we|one) (?:feared|thought|expected))\b", re.IGNORECASE,
)


def classify(question: str, answer: str, evidence: Sequence[Evidence] = ()) -> Assessment:
    """Screen a candidate. Spans are exact, zero-based, end-exclusive source offsets.

    Even a review result is not a verified answer: semantic entailment requires
    independent review. The first exact occurrence of each quotation is reported.
    """
    reasons: list[str] = []
    matches: list[QuoteMatch] = []
    books: set[str] = set()
    if not answer.strip():
        reasons.append("empty_answer")
    qwords, awords = _words(question), _words(answer)
    meaningful_answer = set(awords) - _STOP
    if (qwords and qwords[0] in {"what", "how", "why"} and meaningful_answer
            and meaningful_answer <= set(qwords) - _STOP):
        reasons.append("tautological_answer")
    if _VAGUE.search(answer) or (len(awords) < 5 and len(qwords) > 8):
        reasons.append("vague_or_evasive_answer")
    if not evidence:
        reasons.append("missing_evidence")
    for item in evidence:
        start = item.source_text.find(item.quote) if item.quote.strip() else -1
        if start < 0:
            if "quote_not_found" not in reasons:
                reasons.append("quote_not_found")
            continue
        matches.append(QuoteMatch(item.source_id, item.book, start, start + len(item.quote)))
        if item.book is not None and str(item.book).strip():
            books.add(str(item.book).strip())
        if len(_words(item.quote)) < 5 and "short_quote" not in reasons:
            reasons.append("short_quote")
    if _CHANGE.search(question + " " + answer) and len(books) < 2:
        reasons.append("insufficient_temporal_evidence")
    if evidence and not matches:
        reasons.append("no_verified_quote")
    return Assessment("abstain" if reasons else "review", tuple(reasons), tuple(matches))
