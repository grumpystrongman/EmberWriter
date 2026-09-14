from __future__ import annotations

import re
from typing import Any

WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'’-]*\b")
SENTENCE_RE = re.compile(r"[^.!?]+(?:[.!?]+|$)", re.MULTILINE)

GENERIC_SCAFFOLDS = (
    "a sense of", "a mixture of", "a mix of", "in that moment", "for a moment",
    "couldn't help but", "could not help but", "something shifted", "something changed",
    "the weight of", "the tension between", "the air between", "hung in the air",
    "let out a breath", "released a breath", "it was almost as if", "there was something about",
)


def phrase_hits(text: str) -> list[dict[str, Any]]:
    lowered = text.casefold()
    result: list[dict[str, Any]] = []
    for phrase in GENERIC_SCAFFOLDS:
        start = 0
        while True:
            index = lowered.find(phrase.casefold(), start)
            if index < 0:
                break
            left = max(0, index - 40)
            right = min(len(text), index + len(phrase) + 60)
            result.append({
                "phrase": phrase,
                "start": index,
                "excerpt": re.sub(r"\s+", " ", text[left:right]).strip(),
            })
            start = index + len(phrase)
    return sorted(result, key=lambda item: item["start"])


def symmetry_hits(text: str) -> list[str]:
    pattern = re.compile(r"\bnot\b[^.!?]{1,90}\bbut\b[^.!?]{1,90}[.!?]", re.IGNORECASE)
    return [re.sub(r"\s+", " ", match.group(0)).strip() for match in pattern.finditer(text)][:8]


def cadence_streaks(text: str) -> list[dict[str, Any]]:
    lengths = [len(WORD_RE.findall(match.group(0))) for match in SENTENCE_RE.finditer(text)]
    lengths = [length for length in lengths if length]
    result: list[dict[str, Any]] = []
    index = 0
    while index < len(lengths):
        end = index + 1
        low = high = lengths[index]
        while end < len(lengths):
            low = min(low, lengths[end])
            high = max(high, lengths[end])
            if high - low > 3:
                break
            end += 1
        if end - index >= 4:
            result.append({"start_sentence": index + 1, "sentences": end - index, "range": [min(lengths[index:end]), max(lengths[index:end])]})
        index = max(index + 1, end)
    return result[:8]


def voice_alignment(current: dict[str, float], baseline: dict[str, Any]) -> dict[str, Any] | None:
    if not baseline:
        return None
    tolerances = {
        "avg_sentence_words": 0.35, "sentence_stddev": 0.45,
        "short_sentence_ratio": 0.75, "long_sentence_ratio": 0.75,
        "avg_paragraph_words": 0.50, "dialogue_ratio": 0.65,
        "fragment_ratio": 0.85, "em_dash_rate": 1.20,
    }
    score = 100.0
    deltas: list[dict[str, Any]] = []
    for key, tolerance in tolerances.items():
        if key not in baseline or key not in current:
            continue
        base, now = float(baseline[key]), float(current[key])
        relative = abs(now - base) / max(abs(base), 0.05)
        severity = relative / tolerance
        score -= min(14.0, max(0.0, severity - 0.65) * 7.0)
        if severity >= 1.0:
            deltas.append({"metric": key, "baseline": round(base, 3), "current": round(now, 3), "direction": "higher" if now > base else "lower"})
    score = max(0.0, min(100.0, score))
    label = "close" if score >= 82 else "drifting" if score >= 60 else "far from learned voice"
    return {"score": round(score, 1), "label": label, "deltas": deltas[:8]}
