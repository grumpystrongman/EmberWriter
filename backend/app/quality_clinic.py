"""Transparent, offline manuscript craft & proofreading diagnostics.

Heuristics only: these observations are not an automated grammar authority and
must never delete/replace authored text. Each finding retains a source line
and evidence excerpt. No model calls or third-party language services.
"""
from __future__ import annotations

import re
from collections import Counter

WORD = re.compile(r"\b[A-Za-z][A-Za-z'’-]*\b")
SENTENCE = re.compile(r"(?<=[.!?])\s+")
AI_FILLER = (
    "it was as if", "little did they know", "in that moment",
    "a tapestry of", "the weight of the world", "a testament to",
    "couldn't help but", "for what felt like an eternity",
    "the air crackled with", "a chill ran down",
    "as though the universe", "the silence was deafening",
)
WEAK_PHRASES = (
    "very unique", "completely unanimous", "advance planning",
    "due to the fact that", "in order to", "at this point in time",
    "each and every", "the fact that", "made a decision to",
)
SUSPECT_PASSIVE = re.compile(r"\b(?:was|were|is|are|been|be|being)\s+(?:\w+ly\s+)?[a-z]+(?:ed|en)\b", re.I)
DOUBLE_WORD = re.compile(r"\b([A-Za-z]{2,})\s+\1\b", re.I)
SPACING = re.compile(r"(?<!\.)\s{2,}(?=\S)")
MULTI_PUNCT = re.compile(r"(?<!\.)[!?]{3,}")
WORDY = re.compile(r"\b(?:really|very|quite|rather|somewhat|just|actually|basically|literally)\b", re.I)
DIALOGUE = re.compile(r"[\"“][^\"”]{3,}[\"”]")
STARTS = ("however", "additionally", "moreover", "furthermore", "consequently", "nevertheless")
MAX_FINDINGS = 120


def check_text(text: str) -> dict:
    """Scan prose and return bounded, location-specific craft clues."""
    lines = text.splitlines()
    words = WORD.findall(text)
    sentences = [s.strip() for s in SENTENCE.split(text) if s.strip() and WORD.search(s)]
    lengths = [len(WORD.findall(s)) for s in sentences]
    lines_total = len(lines)
    results: list[dict] = []
    seen: set[tuple[str, int, str]] = set()

    def add(category: str, severity: str, line: int, snippet: str, message: str) -> None:
        if len(results) >= MAX_FINDINGS:
            return
        key = (category, line, message)
        if key in seen:
            return
        seen.add(key)
        results.append({
            "category": category,
            "severity": severity,
            "line": line,
            "excerpt": snippet.strip()[:190],
            "message": message,
        })

    for i, line in enumerate(lines, 1):
        lowered = line.casefold()
        if len(line) > 1600:
            add("clarity", "notice", i, line, "Long paragraph line; consider checking paragraph breaks and readability.")
        for match in DOUBLE_WORD.finditer(line):
            add("proofreading", "likely_error", i, line, f"Repeated word '{match.group(1)}' may be a typo.")
        for match in SPACING.finditer(line):
            # Indentation in scripts, poetry, dialogue and lists is legitimate.
            if match.start() > 1 and not line.lstrip().startswith((">", "-", "*", "#")):
                add("proofreading", "notice", i, line, "Unexpected multiple spaces within a sentence.")
        if MULTI_PUNCT.search(line):
            add("punctuation", "notice", i, line, "Three or more repeated punctuation marks; check intentional emphasis.")
        for phrase in AI_FILLER:
            if phrase in lowered:
                add("AI-pattern", "notice", i, line,
                    f"Familiar generated-sounding phrase: '{phrase}'. Keep if it fits the author's distinctive voice.")
        for phrase in WEAK_PHRASES:
            if phrase in lowered:
                add("wordiness", "notice", i, line,
                    f"Wordy or redundant phrasing: '{phrase}'. Consider a more specific alternative.")
        passive = list(SUSPECT_PASSIVE.finditer(line))
        if len(passive) >= 2:
            add("syntax", "notice", i, line,
                "Several possible passive constructions. Check whether the sentence hides who acts.")
        if len(WORDY.findall(line)) >= 4:
            add("wordiness", "notice", i, line,
                "High concentration of intensifiers or hedges; verify that each adds meaning.")

    sentence_beginnings = Counter(
        " ".join(w.casefold() for w in WORD.findall(s)[:3])
        for s in sentences if len(WORD.findall(s)) >= 3
    )
    repeated_starts = {key: count for key, count in sentence_beginnings.items() if count >= 3}
    if repeated_starts:
        add("rhythm", "notice", 0, "",
            "Multiple sentences share the same first three words: " + ", ".join(f"{k} ×{v}" for k, v in list(repeated_starts.items())[:5]))
    transition_starts = sum(1 for s in sentences if WORD.findall(s) and WORD.findall(s)[0].casefold() in STARTS)
    if len(sentences) >= 12 and transition_starts / len(sentences) > .16:
        add("structure", "notice", 0, "",
            "Many sentences start with explanatory transition words; consider more varied entry points.")
    if lengths and len(lengths) >= 8:
        if max(lengths) - min(lengths) < 7:
            add("rhythm", "notice", 0, "",
                "Sentence lengths cluster tightly; deliberate variation could improve cadence.")
        if max(lengths) > 65:
            add("clarity", "notice", 0, "",
                f"At least one sentence is unusually long ({max(lengths)} words); check its syntactic control.")
    if len(words) > 300 and text.count("—") > len(words) / 130:
        add("punctuation", "notice", 0, "",
            "High em-dash density. Consider whether every break serves character voice or pacing.")
    distinct = len({w.casefold() for w in words})
    metrics = {
        "words": len(words),
        "sentences": len(sentences),
        "lines": lines_total,
        "average_sentence_words": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "longest_sentence_words": max(lengths, default=0),
        "unique_word_ratio": round(distinct / len(words), 3) if words else 0,
        "dialogue_passages": len(DIALOGUE.findall(text)),
        "suspected_passives": len(SUSPECT_PASSIVE.findall(text)),
        "em_dashes": text.count("—"),
        "findings": len(results),
    }
    return {"metrics": metrics, "findings": results, "truncated": len(results) >= MAX_FINDINGS,
            "method": "offline transparent heuristics, not authoritative grammar correction"}
