from __future__ import annotations

import re
from collections import Counter

AI_TELLS = (
    "a mix of",
    "a mixture of",
    "in that moment",
    "for a moment",
    "couldn't help but",
    "could not help but",
    "something shifted",
    "something changed",
    "the weight of",
    "the tension between",
    "the air between",
    "hung in the air",
    "let out a breath",
    "released a breath",
    "he didn't realize he'd been holding",
    "she didn't realize she'd been holding",
    "it was almost as if",
    "there was something about",
)

EMOTION_LABELS = (
    "anger", "angry", "fear", "afraid", "sad", "sadness", "happy", "happiness",
    "desire", "wanted", "need", "needed", "nervous", "anxious", "jealous", "jealousy",
)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part.strip()]


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text.lower())


def diagnose_prose(text: str) -> list[str]:
    if not text.strip():
        return []
    lowered = text.lower()
    issues: list[str] = []

    tell_hits = [(phrase, lowered.count(phrase)) for phrase in AI_TELLS if lowered.count(phrase)]
    repeated_tells = [f"'{phrase}' x{count}" for phrase, count in tell_hits if count >= 1]
    if repeated_tells:
        issues.append("Generic/AI-associated phrasing appears: " + ", ".join(repeated_tells[:8]))

    sentences = _sentences(text)
    starts = Counter(" ".join(_words(sentence)[:3]) for sentence in sentences if len(_words(sentence)) >= 3)
    repeated_starts = [(start, count) for start, count in starts.items() if start and count >= 3]
    if repeated_starts:
        issues.append(
            "Repeated sentence openings reduce natural cadence: "
            + ", ".join(f"'{start}' x{count}" for start, count in repeated_starts[:6])
        )

    labels = Counter(word for word in _words(text) if word in EMOTION_LABELS)
    repeated_labels = [(word, count) for word, count in labels.items() if count >= 3]
    if repeated_labels:
        issues.append(
            "Emotion is repeatedly named instead of varied through behavior/interiority: "
            + ", ".join(f"{word} x{count}" for word, count in repeated_labels[:6])
        )

    adverbs = re.findall(r"\b[A-Za-z]{4,}ly\b", text, flags=re.IGNORECASE)
    if len(adverbs) >= max(5, len(sentences) // 3):
        issues.append(f"Adverb density is high ({len(adverbs)} likely -ly adverbs); strengthen verbs selectively rather than deleting them mechanically.")

    dialogue = re.findall(r"[\"“][^\"”]+[\"”]", text)
    if dialogue:
        generic_tags = len(re.findall(r"\b(?:said softly|whispered softly|said quietly|asked softly|murmured softly)\b", lowered))
        if generic_tags >= 2:
            issues.append("Dialogue repeatedly relies on generic soft/quiet delivery tags; differentiate character performance and subtext.")

    body_repetition = Counter(
        match.group(1).lower()
        for match in re.finditer(r"\b(eyes|breath|heart|pulse|hands|fingers|mouth|lips|chest|stomach)\b", lowered)
    )
    repetitive_body = [(term, count) for term, count in body_repetition.items() if count >= 6]
    if repetitive_body:
        issues.append(
            "Physical reaction vocabulary is clustering: "
            + ", ".join(f"{term} x{count}" for term, count in repetitive_body[:6])
            + ". Vary only where the repetition is not intentional."
        )

    short = sum(1 for sentence in sentences if len(_words(sentence)) <= 5)
    medium = sum(1 for sentence in sentences if 6 <= len(_words(sentence)) <= 20)
    long = sum(1 for sentence in sentences if len(_words(sentence)) >= 21)
    if len(sentences) >= 8 and (short == 0 or long == 0):
        issues.append(
            f"Cadence variety may be too even ({short} short / {medium} medium / {long} long sentences); compare against the learned author fingerprint before smoothing further."
        )

    paragraphs = [part for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]
    if len(paragraphs) >= 5:
        lengths = [len(_words(paragraph)) for paragraph in paragraphs]
        if max(lengths) - min(lengths) < 18:
            issues.append("Paragraph lengths are unusually uniform; preserve natural paragraph rhythm rather than evenly sized blocks.")

    return issues[:10]


def quality_guidance(text: str) -> str:
    issues = diagnose_prose(text)
    if not issues:
        return "No deterministic prose-quality warnings were found. Preserve the draft unless a revision clearly improves voice or precision."
    return "\n".join(f"- {issue}" for issue in issues)
