from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from uuid import uuid4

from .binder import get_binder
from .editorial_models import EditorialProfile, EditorialRunRequest
from .storage import project_root, read_text, save_text, utc_now

EDITORIAL_PROFILE_PATH = "style/editorial-profile.json"

REPORTS: tuple[dict[str, Any], ...] = (
    {
        "id": "repeated_word",
        "name": "Repeated Words",
        "category": "repetition",
        "description": "Finds accidentally repeated adjacent words such as 'the the'.",
        "default_enabled": True,
    },
    {
        "id": "repeated_phrase",
        "name": "Repeated Phrases",
        "category": "repetition",
        "description": "Finds recurring three-word phrases that may make prose feel recycled.",
        "default_enabled": True,
    },
    {
        "id": "adverb",
        "name": "Adverbs",
        "category": "word_choice",
        "description": "Highlights likely -ly adverbs for deliberate review rather than automatic removal.",
        "default_enabled": True,
    },
    {
        "id": "filler_word",
        "name": "Filler Words",
        "category": "word_choice",
        "description": "Finds common intensifiers and hedges that can weaken otherwise precise prose.",
        "default_enabled": True,
    },
    {
        "id": "filter_word",
        "name": "Filter Words",
        "category": "point_of_view",
        "description": "Highlights perception/thought filters that may add distance in close point of view.",
        "default_enabled": True,
    },
    {
        "id": "passive_voice",
        "name": "Passive Voice",
        "category": "clarity",
        "description": "Flags likely passive constructions using a conservative grammatical heuristic.",
        "default_enabled": True,
    },
    {
        "id": "weak_verb_cluster",
        "name": "Weak Verb Clusters",
        "category": "word_choice",
        "description": "Finds sentences with several linking/weak verbs that may benefit from stronger action.",
        "default_enabled": True,
    },
    {
        "id": "sentence_length",
        "name": "Sentence Length",
        "category": "rhythm",
        "description": "Finds unusually long sentences and very short fragments using project thresholds.",
        "default_enabled": True,
    },
    {
        "id": "paragraph_length",
        "name": "Paragraph Length",
        "category": "rhythm",
        "description": "Finds dense paragraphs that may slow visual pacing or bury a beat.",
        "default_enabled": True,
    },
    {
        "id": "sentence_start",
        "name": "Repeated Sentence Starts",
        "category": "rhythm",
        "description": "Finds runs of sentences beginning with the same word.",
        "default_enabled": True,
    },
    {
        "id": "sticky_sentence",
        "name": "Sticky Sentences",
        "category": "clarity",
        "description": "Finds sentences with a high share of glue/function words.",
        "default_enabled": True,
    },
    {
        "id": "redundancy",
        "name": "Redundancies",
        "category": "clarity",
        "description": "Finds common wordy or redundant constructions with tighter alternatives.",
        "default_enabled": True,
    },
    {
        "id": "cliche",
        "name": "Cliches",
        "category": "style",
        "description": "Finds a curated set of common stock phrases for intentional review.",
        "default_enabled": True,
    },
    {
        "id": "dialogue_adverb",
        "name": "Dialogue Adverbs",
        "category": "dialogue",
        "description": "Finds dialogue tags immediately modified by likely adverbs.",
        "default_enabled": True,
    },
    {
        "id": "dialogue_balance",
        "name": "Dialogue Balance",
        "category": "dialogue",
        "description": "Measures the proportion of quoted dialogue within each analyzed document.",
        "default_enabled": True,
    },
    {
        "id": "readability",
        "name": "Readability",
        "category": "readability",
        "description": "Computes a Flesch-style readability score and flags unusually dense prose.",
        "default_enabled": True,
    },
    {
        "id": "punctuation",
        "name": "Punctuation Emphasis",
        "category": "style",
        "description": "Finds repeated exclamation/question marks and extended ellipses.",
        "default_enabled": True,
    },
)
REPORT_MAP = {item["id"]: item for item in REPORTS}

FILLER_WORDS = {
    "actually",
    "basically",
    "certainly",
    "definitely",
    "just",
    "literally",
    "maybe",
    "perhaps",
    "quite",
    "rather",
    "really",
    "simply",
    "somehow",
    "somewhat",
    "suddenly",
    "totally",
    "very",
}
FILTER_WORDS = {
    "appeared",
    "felt",
    "heard",
    "knew",
    "looked",
    "noticed",
    "realized",
    "saw",
    "seemed",
    "thought",
    "watched",
    "wondered",
}
ADVERB_EXCEPTIONS = {
    "ally",
    "apply",
    "belly",
    "early",
    "family",
    "friendly",
    "holy",
    "jelly",
    "likely",
    "lonely",
    "lovely",
    "only",
    "reply",
    "silly",
    "supply",
    "ugly",
}
WEAK_VERBS = {"am", "are", "be", "been", "being", "felt", "is", "seem", "seemed", "was", "were"}
GLUE_WORDS = {
    "a", "about", "after", "all", "also", "am", "an", "and", "any", "are", "as", "at",
    "be", "because", "been", "before", "being", "but", "by", "can", "could", "did", "do",
    "does", "each", "for", "from", "had", "has", "have", "he", "her", "hers", "him", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "may", "me", "might", "more", "most",
    "my", "no", "not", "of", "on", "one", "or", "our", "out", "she", "so", "some", "than",
    "that", "the", "their", "them", "then", "there", "these", "they", "this", "those", "to",
    "too", "up", "us", "was", "we", "were", "what", "when", "which", "who", "will", "with",
    "would", "you", "your",
}
STOP_PHRASE_WORDS = GLUE_WORDS | {"said", "asked"}
IRREGULAR_PARTICIPLES = {
    "beaten", "begun", "bent", "bitten", "blown", "broken", "built", "bought", "brought",
    "caught", "chosen", "come", "cut", "done", "drawn", "driven", "eaten", "fallen", "felt",
    "found", "given", "gone", "grown", "heard", "held", "kept", "known", "laid", "led", "left",
    "lost", "made", "met", "paid", "read", "run", "said", "seen", "sent", "set", "shown", "sold",
    "spoken", "spent", "stood", "taken", "taught", "told", "thought", "thrown", "understood", "won",
    "worn", "written",
}
REDUNDANCIES = {
    "at this point in time": "now",
    "began to": "often the direct verb",
    "close proximity": "proximity",
    "completely finished": "finished",
    "due to the fact that": "because",
    "each and every": "each or every",
    "end result": "result",
    "free gift": "gift",
    "in order to": "to",
    "past history": "history",
    "started to": "often the direct verb",
    "very unique": "unique",
}
CLICHES = {
    "at the end of the day",
    "avoid it like the plague",
    "beat around the bush",
    "better late than never",
    "blood ran cold",
    "breath caught in",
    "calm before the storm",
    "dead as a doornail",
    "eyes like saucers",
    "few and far between",
    "heart skipped a beat",
    "in the nick of time",
    "last but not least",
    "light at the end of the tunnel",
    "like a moth to a flame",
    "needle in a haystack",
    "read between the lines",
    "ripped through him",
    "ripped through her",
    "shiver ran down",
    "sick and tired",
    "the tip of the iceberg",
    "time stood still",
    "weak in the knees",
}
DIALOGUE_TAGS = {
    "asked", "breathed", "called", "cried", "growled", "hissed", "murmured", "replied", "said",
    "shouted", "snapped", "whispered", "yelled",
}
WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'’-]*\b")
SENTENCE_RE = re.compile(r"[^.!?]+(?:[.!?]+|$)", re.MULTILINE)
PARAGRAPH_RE = re.compile(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", re.DOTALL)


def report_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in REPORTS]


def default_profile() -> EditorialProfile:
    return EditorialProfile(enabled_reports=[item["id"] for item in REPORTS if item["default_enabled"]])


def get_editorial_profile(slug: str) -> EditorialProfile:
    try:
        raw = json.loads(read_text(slug, EDITORIAL_PROFILE_PATH))
        profile = EditorialProfile.model_validate(raw)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        profile = default_profile()
    valid = [report_id for report_id in profile.enabled_reports if report_id in REPORT_MAP]
    if not valid:
        valid = default_profile().enabled_reports
    return profile.model_copy(update={"enabled_reports": valid})


def save_editorial_profile(slug: str, profile: EditorialProfile) -> EditorialProfile:
    invalid = sorted(set(profile.enabled_reports) - set(REPORT_MAP))
    if invalid:
        raise ValueError(f"Unknown editorial report(s): {', '.join(invalid)}")
    save_text(slug, EDITORIAL_PROFILE_PATH, json.dumps(profile.model_dump(), indent=2, ensure_ascii=False))
    return profile


def _db_path(slug: str) -> Path:
    path = project_root(slug) / ".ember" / "story.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect(slug: str) -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(slug))
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS editorial_runs (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            scope TEXT NOT NULL,
            path TEXT,
            reports_json TEXT NOT NULL,
            project_hash TEXT NOT NULL,
            documents INTEGER NOT NULL,
            words INTEGER NOT NULL,
            findings INTEGER NOT NULL,
            summary_json TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS editorial_findings (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            report_id TEXT NOT NULL,
            severity TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            path TEXT NOT NULL,
            binder_node_id TEXT,
            start_offset INTEGER NOT NULL,
            end_offset INTEGER NOT NULL,
            line INTEGER NOT NULL,
            excerpt TEXT NOT NULL,
            anchor_text TEXT NOT NULL,
            message TEXT NOT NULL,
            suggestion TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_editorial_findings_run ON editorial_findings(run_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_editorial_findings_path ON editorial_findings(path)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_editorial_findings_report ON editorial_findings(report_id)")
    con.commit()
    return con


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean_for_analysis(source: str) -> str:
    chars = list(source)
    for match in re.finditer(r"<[^>]+>", source):
        for index in range(match.start(), match.end()):
            if chars[index] != "\n":
                chars[index] = " "
    for match in re.finditer(r"\]\([^\n)]*\)", source):
        for index in range(match.start(), match.end()):
            if chars[index] != "\n":
                chars[index] = " "
    for index, char in enumerate(chars):
        if char in "#*_`~[]>()":
            chars[index] = " "
    return "".join(chars)


def _line_number(source: str, start: int) -> int:
    return source.count("\n", 0, max(0, start)) + 1


def _normalize_excerpt(text: str, limit: int = 240) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _anchor(text: str, limit: int = 90) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[:limit].rsplit(" ", 1)[0] or compact[:limit]


def _finding(
    report_id: str,
    source: str,
    start: int,
    end: int,
    *,
    severity: str,
    message: str,
    suggestion: str,
    anchor_text: str | None = None,
) -> dict[str, Any]:
    definition = REPORT_MAP[report_id]
    excerpt_start = max(0, source.rfind("\n", 0, start) + 1)
    newline = source.find("\n", end)
    excerpt_end = len(source) if newline < 0 else newline
    raw_excerpt = source[excerpt_start:excerpt_end].strip() or source[start:end]
    raw_anchor = anchor_text or source[start:end]
    return {
        "report_id": report_id,
        "report_name": definition["name"],
        "category": definition["category"],
        "severity": severity,
        "start_offset": max(0, start),
        "end_offset": max(start, end),
        "line": _line_number(source, start),
        "excerpt": _normalize_excerpt(raw_excerpt),
        "anchor_text": _anchor(raw_anchor),
        "message": message,
        "suggestion": suggestion,
    }


def _word_spans(text: str) -> list[tuple[str, int, int]]:
    return [(match.group(0), match.start(), match.end()) for match in WORD_RE.finditer(text)]


def _sentence_spans(text: str) -> list[tuple[int, int, str]]:
    result: list[tuple[int, int, str]] = []
    for match in SENTENCE_RE.finditer(text):
        raw = match.group(0)
        left = len(raw) - len(raw.lstrip())
        right = len(raw.rstrip())
        start = match.start() + left
        end = match.start() + right
        if end > start and WORD_RE.search(text[start:end]):
            result.append((start, end, text[start:end]))
    return result


def _paragraph_spans(text: str) -> list[tuple[int, int, str]]:
    result: list[tuple[int, int, str]] = []
    for match in PARAGRAPH_RE.finditer(text):
        start, end = match.span()
        if WORD_RE.search(text[start:end]):
            result.append((start, end, text[start:end]))
    return result


def _repeated_word(source: str, text: str) -> list[dict[str, Any]]:
    findings = []
    pattern = re.compile(r"\b([A-Za-z][A-Za-z'’-]*)\b(?:\s+|[,;:]\s*)\1\b", re.IGNORECASE)
    for match in pattern.finditer(text):
        findings.append(
            _finding(
                "repeated_word",
                source,
                match.start(),
                match.end(),
                severity="strong",
                message=f"'{match.group(1)}' is repeated back-to-back.",
                suggestion="Remove one occurrence unless the repetition is intentional for voice or emphasis.",
                anchor_text=source[match.start():match.end()],
            )
        )
    return findings


def _repeated_phrase(source: str, text: str, minimum: int) -> list[dict[str, Any]]:
    words = [(word.casefold(), start, end) for word, start, end in _word_spans(text)]
    occurrences: dict[tuple[str, str, str], list[tuple[int, int]]] = defaultdict(list)
    for index in range(len(words) - 2):
        phrase = (words[index][0], words[index + 1][0], words[index + 2][0])
        if all(word in STOP_PHRASE_WORDS for word in phrase):
            continue
        occurrences[phrase].append((words[index][1], words[index + 2][2]))
    repeated = sorted(
        ((phrase, spans) for phrase, spans in occurrences.items() if len(spans) >= minimum),
        key=lambda item: (-len(item[1]), item[1][0][0]),
    )[:40]
    findings = []
    for phrase, spans in repeated:
        display = " ".join(phrase)
        for start, end in spans[1:6]:
            findings.append(
                _finding(
                    "repeated_phrase",
                    source,
                    start,
                    end,
                    severity="warning",
                    message=f"The phrase '{display}' appears {len(spans)} times in this document.",
                    suggestion="Check whether the repetition is a deliberate motif or an accidental prose echo.",
                    anchor_text=source[start:end],
                )
            )
    return findings


def _word_list_report(
    report_id: str,
    source: str,
    text: str,
    words: set[str],
    message_template: str,
    suggestion: str,
    severity: str = "info",
) -> list[dict[str, Any]]:
    findings = []
    for match in WORD_RE.finditer(text):
        lowered = match.group(0).casefold()
        if lowered in words:
            findings.append(
                _finding(
                    report_id,
                    source,
                    match.start(),
                    match.end(),
                    severity=severity,
                    message=message_template.format(word=match.group(0)),
                    suggestion=suggestion,
                    anchor_text=source[match.start():match.end()],
                )
            )
    return findings


def _adverbs(source: str, text: str) -> list[dict[str, Any]]:
    findings = []
    for match in WORD_RE.finditer(text):
        word = match.group(0)
        lowered = word.casefold()
        if len(lowered) < 5 or not lowered.endswith("ly") or lowered in ADVERB_EXCEPTIONS:
            continue
        findings.append(
            _finding(
                "adverb",
                source,
                match.start(),
                match.end(),
                severity="info",
                message=f"'{word}' is a likely adverb.",
                suggestion="Keep it if it sharpens voice; otherwise test whether the verb or surrounding image can carry the meaning.",
                anchor_text=source[match.start():match.end()],
            )
        )
    return findings


def _passive_voice(source: str, text: str) -> list[dict[str, Any]]:
    findings = []
    be = r"(?:am|is|are|was|were|be|been|being)"
    pattern = re.compile(rf"\b{be}\b(?:\s+\w+ly)?\s+([A-Za-z][A-Za-z'’-]*)", re.IGNORECASE)
    for match in pattern.finditer(text):
        participle = match.group(1).casefold()
        if not (participle.endswith(("ed", "en")) or participle in IRREGULAR_PARTICIPLES):
            continue
        findings.append(
            _finding(
                "passive_voice",
                source,
                match.start(),
                match.end(),
                severity="warning",
                message="This is a likely passive construction.",
                suggestion="Check whether naming the actor and using an active verb would make the beat clearer or stronger.",
                anchor_text=source[match.start():match.end()],
            )
        )
    return findings


def _weak_verb_clusters(source: str, text: str) -> list[dict[str, Any]]:
    findings = []
    for start, end, sentence in _sentence_spans(text):
        words = [match.group(0).casefold() for match in WORD_RE.finditer(sentence)]
        count = sum(word in WEAK_VERBS for word in words)
        if count < 3:
            continue
        findings.append(
            _finding(
                "weak_verb_cluster",
                source,
                start,
                end,
                severity="warning",
                message=f"This sentence contains {count} linking or weak verbs.",
                suggestion="Look for one or two places where a more specific action or image can carry the sentence.",
                anchor_text=source[start:end],
            )
        )
    return findings


def _sentence_lengths(source: str, text: str, profile: EditorialProfile) -> list[dict[str, Any]]:
    findings = []
    for start, end, sentence in _sentence_spans(text):
        count = len(WORD_RE.findall(sentence))
        if count >= profile.long_sentence_words:
            severity = "strong" if count >= math.ceil(profile.long_sentence_words * 1.6) else "warning"
            findings.append(
                _finding(
                    "sentence_length",
                    source,
                    start,
                    end,
                    severity=severity,
                    message=f"Long sentence: {count} words (project threshold {profile.long_sentence_words}).",
                    suggestion="Check the sentence's turns and emphasis. Split only if the current length blurs the intended rhythm.",
                    anchor_text=source[start:end],
                )
            )
        elif 0 < count <= profile.short_sentence_words:
            findings.append(
                _finding(
                    "sentence_length",
                    source,
                    start,
                    end,
                    severity="info",
                    message=f"Very short sentence: {count} words.",
                    suggestion="Short sentences can hit hard. Confirm this fragment or beat earns the emphasis.",
                    anchor_text=source[start:end],
                )
            )
    return findings


def _paragraph_lengths(source: str, text: str, profile: EditorialProfile) -> list[dict[str, Any]]:
    findings = []
    for start, end, paragraph in _paragraph_spans(text):
        count = len(WORD_RE.findall(paragraph))
        if count < profile.long_paragraph_words:
            continue
        severity = "strong" if count >= profile.long_paragraph_words * 2 else "warning"
        findings.append(
            _finding(
                "paragraph_length",
                source,
                start,
                end,
                severity=severity,
                message=f"Dense paragraph: {count} words (project threshold {profile.long_paragraph_words}).",
                suggestion="Check whether a new action, speaker, image, or emotional turn deserves its own paragraph.",
                anchor_text=source[start:end],
            )
        )
    return findings


def _sentence_starts(source: str, text: str) -> list[dict[str, Any]]:
    sentences = _sentence_spans(text)
    starts: list[tuple[str, int, int, str]] = []
    for start, end, sentence in sentences:
        word_match = WORD_RE.search(sentence)
        if word_match:
            starts.append((word_match.group(0).casefold(), start, end, sentence))
    findings = []
    index = 0
    while index < len(starts):
        word = starts[index][0]
        end_index = index + 1
        while end_index < len(starts) and starts[end_index][0] == word:
            end_index += 1
        run = starts[index:end_index]
        if len(run) >= 3:
            start = run[0][1]
            end = run[-1][2]
            findings.append(
                _finding(
                    "sentence_start",
                    source,
                    start,
                    end,
                    severity="warning",
                    message=f"{len(run)} consecutive sentences begin with '{word}'.",
                    suggestion="Vary the opening structure if the repetition is not creating an intentional rhetorical rhythm.",
                    anchor_text=source[run[-1][1]:run[-1][2]],
                )
            )
        index = end_index
    return findings


def _sticky_sentences(source: str, text: str, profile: EditorialProfile) -> list[dict[str, Any]]:
    findings = []
    for start, end, sentence in _sentence_spans(text):
        words = [match.group(0).casefold() for match in WORD_RE.finditer(sentence)]
        if len(words) < 10:
            continue
        glue = sum(word in GLUE_WORDS for word in words)
        percent = glue * 100 / len(words)
        if percent < profile.sticky_sentence_percent:
            continue
        findings.append(
            _finding(
                "sticky_sentence",
                source,
                start,
                end,
                severity="warning",
                message=f"Glue-word density is {percent:.0f}% ({glue} of {len(words)} words).",
                suggestion="Look for a clearer subject, stronger verb, or a shorter route through the sentence; keep it if the cadence is intentional.",
                anchor_text=source[start:end],
            )
        )
    return findings


def _phrase_report(
    report_id: str,
    source: str,
    text: str,
    phrases: Iterable[str],
    suggestion_for: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    findings = []
    for phrase in sorted(phrases, key=len, reverse=True):
        for match in re.finditer(rf"\b{re.escape(phrase)}\b", text, flags=re.IGNORECASE):
            alternative = suggestion_for.get(phrase) if suggestion_for else None
            findings.append(
                _finding(
                    report_id,
                    source,
                    match.start(),
                    match.end(),
                    severity="info" if report_id == "cliche" else "warning",
                    message=(
                        f"'{source[match.start():match.end()]}' is a common stock phrase."
                        if report_id == "cliche"
                        else f"'{source[match.start():match.end()]}' is potentially redundant or wordy."
                    ),
                    suggestion=(
                        "If this is not character-specific or deliberately familiar, replace it with an image or phrasing native to this book."
                        if report_id == "cliche"
                        else f"Consider {alternative}." if alternative else "Consider a tighter construction."
                    ),
                    anchor_text=source[match.start():match.end()],
                )
            )
    return findings


def _dialogue_adverbs(source: str, text: str) -> list[dict[str, Any]]:
    findings = []
    tag_group = "|".join(sorted(DIALOGUE_TAGS))
    pattern = re.compile(
        rf"[\"“][^\"”\n]{{1,500}}[\"”]\s*(?:[,;:]?\s*)?(?:\w+\s+)?({tag_group})\s+([A-Za-z]+ly)\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        adverb_start, adverb_end = match.span(2)
        findings.append(
            _finding(
                "dialogue_adverb",
                source,
                adverb_start,
                adverb_end,
                severity="info",
                message=f"Dialogue tag '{match.group(1)}' is modified by '{match.group(2)}'.",
                suggestion="Check whether the dialogue, action beat, or context already communicates the delivery.",
                anchor_text=source[adverb_start:adverb_end],
            )
        )
    return findings


def _dialogue_balance(source: str, text: str, profile: EditorialProfile) -> tuple[list[dict[str, Any]], dict[str, float]]:
    total_words = len(WORD_RE.findall(text))
    dialogue_words = 0
    for match in re.finditer(r"[\"“]([^\"”]+)[\"”]", text, flags=re.DOTALL):
        dialogue_words += len(WORD_RE.findall(match.group(1)))
    percent = dialogue_words * 100 / total_words if total_words else 0.0
    findings: list[dict[str, Any]] = []
    if total_words >= 100 and percent < profile.dialogue_low_percent:
        findings.append(
            _finding(
                "dialogue_balance",
                source,
                0,
                min(len(source), 120),
                severity="info",
                message=f"Dialogue is {percent:.1f}% of this document, below the project low marker of {profile.dialogue_low_percent:.1f}%.",
                suggestion="This may be exactly right for the scene. Review whether any exposition would gain energy from character interaction.",
                anchor_text=source[:120],
            )
        )
    elif total_words >= 100 and percent > profile.dialogue_high_percent:
        findings.append(
            _finding(
                "dialogue_balance",
                source,
                0,
                min(len(source), 120),
                severity="info",
                message=f"Dialogue is {percent:.1f}% of this document, above the project high marker of {profile.dialogue_high_percent:.1f}%.",
                suggestion="Check whether setting, action, interiority, or physical beats need more room between exchanges.",
                anchor_text=source[:120],
            )
        )
    return findings, {"dialogue_percent": round(percent, 2)}


def _syllables(word: str) -> int:
    cleaned = re.sub(r"[^a-z]", "", word.casefold())
    if not cleaned:
        return 0
    groups = re.findall(r"[aeiouy]+", cleaned)
    count = len(groups)
    if cleaned.endswith("e") and count > 1 and not cleaned.endswith(("le", "ye")):
        count -= 1
    return max(1, count)


def _readability(source: str, text: str) -> tuple[list[dict[str, Any]], dict[str, float]]:
    words = [match.group(0) for match in WORD_RE.finditer(text)]
    sentences = _sentence_spans(text)
    if not words or not sentences:
        return [], {"readability": 0.0}
    syllables = sum(_syllables(word) for word in words)
    score = 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (syllables / len(words))
    findings = []
    if len(words) >= 100 and score < 35:
        findings.append(
            _finding(
                "readability",
                source,
                0,
                min(len(source), 120),
                severity="warning",
                message=f"Readability score is {score:.1f}, indicating unusually dense prose by this heuristic.",
                suggestion="Check sentence structure and word complexity. Genre voice can justify density; use this as a diagnostic, not a target score.",
                anchor_text=source[:120],
            )
        )
    return findings, {"readability": round(score, 2)}


def _punctuation(source: str, text: str) -> list[dict[str, Any]]:
    findings = []
    for match in re.finditer(r"!{2,}|\?{2,}|\.{4,}", text):
        findings.append(
            _finding(
                "punctuation",
                source,
                match.start(),
                match.end(),
                severity="info",
                message=f"Repeated punctuation: '{source[match.start():match.end()]}'.",
                suggestion="Keep it when it belongs to the book's voice; otherwise a single mark usually carries more authority.",
                anchor_text=source[match.start():match.end()],
            )
        )
    return findings


def analyze_text(source: str, reports: list[str], profile: EditorialProfile) -> tuple[list[dict[str, Any]], dict[str, float | int]]:
    text = _clean_for_analysis(source)
    findings: list[dict[str, Any]] = []
    metrics: dict[str, float | int] = {
        "words": len(WORD_RE.findall(text)),
        "sentences": len(_sentence_spans(text)),
        "paragraphs": len(_paragraph_spans(text)),
    }
    selected = set(reports)
    if "repeated_word" in selected:
        findings.extend(_repeated_word(source, text))
    if "repeated_phrase" in selected:
        findings.extend(_repeated_phrase(source, text, profile.repeated_phrase_minimum))
    if "adverb" in selected:
        findings.extend(_adverbs(source, text))
    if "filler_word" in selected:
        findings.extend(
            _word_list_report(
                "filler_word",
                source,
                text,
                FILLER_WORDS,
                "'{word}' can function as a filler, hedge, or generic intensifier.",
                "Check whether deleting it or choosing a more specific image/verb strengthens the sentence.",
            )
        )
    if "filter_word" in selected:
        findings.extend(
            _word_list_report(
                "filter_word",
                source,
                text,
                FILTER_WORDS,
                "'{word}' may filter experience through the viewpoint character instead of presenting it directly.",
                "In close POV, test the sentence without the filter. Keep it when the act of perceiving or thinking matters.",
            )
        )
    if "passive_voice" in selected:
        findings.extend(_passive_voice(source, text))
    if "weak_verb_cluster" in selected:
        findings.extend(_weak_verb_clusters(source, text))
    if "sentence_length" in selected:
        findings.extend(_sentence_lengths(source, text, profile))
    if "paragraph_length" in selected:
        findings.extend(_paragraph_lengths(source, text, profile))
    if "sentence_start" in selected:
        findings.extend(_sentence_starts(source, text))
    if "sticky_sentence" in selected:
        findings.extend(_sticky_sentences(source, text, profile))
    if "redundancy" in selected:
        findings.extend(_phrase_report("redundancy", source, text, REDUNDANCIES, REDUNDANCIES))
    if "cliche" in selected:
        findings.extend(_phrase_report("cliche", source, text, CLICHES))
    if "dialogue_adverb" in selected:
        findings.extend(_dialogue_adverbs(source, text))
    if "dialogue_balance" in selected:
        result, values = _dialogue_balance(source, text, profile)
        findings.extend(result)
        metrics.update(values)
    if "readability" in selected:
        result, values = _readability(source, text)
        findings.extend(result)
        metrics.update(values)
    if "punctuation" in selected:
        findings.extend(_punctuation(source, text))
    findings.sort(key=lambda item: (item["start_offset"], item["report_id"]))
    return findings, metrics


def _draft_documents(slug: str) -> list[dict[str, str]]:
    state = get_binder(slug)
    node_map = {node.id: node for node in state.nodes}
    draft = next((node_map[node_id] for node_id in state.roots if node_map[node_id].title == "Draft"), None)
    if draft is None:
        raise ValueError("Binder Draft root is missing")
    children: dict[str, list[Any]] = defaultdict(list)
    for node in state.nodes:
        if node.parent_id:
            children[node.parent_id].append(node)
    for nodes in children.values():
        nodes.sort(key=lambda node: node.position)
    result: list[dict[str, str]] = []

    def visit(parent_id: str) -> None:
        for node in children.get(parent_id, []):
            if node.kind == "folder":
                visit(node.id)
                continue
            if not node.path or node.custom_metadata.get("source_missing"):
                continue
            result.append({"path": node.path, "binder_node_id": node.id})

    visit(draft.id)
    return result


def _documents_for_run(slug: str, request: EditorialRunRequest) -> list[dict[str, str]]:
    if request.scope == "draft":
        documents = _draft_documents(slug)
        if not documents:
            raise ValueError("Draft does not contain readable documents")
        return documents
    path = request.path or ""
    state = get_binder(slug)
    node = next((item for item in state.nodes if item.path == path), None)
    read_text(slug, path)
    return [{"path": path, "binder_node_id": node.id if node else ""}]


def run_editorial(slug: str, request: EditorialRunRequest) -> dict[str, Any]:
    profile = get_editorial_profile(slug)
    reports = request.reports or profile.enabled_reports
    invalid = sorted(set(reports) - set(REPORT_MAP))
    if invalid:
        raise ValueError(f"Unknown editorial report(s): {', '.join(invalid)}")
    reports = list(dict.fromkeys(reports))
    documents = _documents_for_run(slug, request)
    run_id = uuid4().hex
    created_at = utc_now()
    all_findings: list[dict[str, Any]] = []
    source_hashes: list[str] = []
    metrics_totals: dict[str, float] = defaultdict(float)
    total_words = 0

    for document in documents:
        path = document["path"]
        source = read_text(slug, path)
        source_hash = _hash(source)
        source_hashes.append(f"{path}:{source_hash}")
        findings, metrics = analyze_text(source, reports, profile)
        total_words += int(metrics.get("words", 0))
        for key in ("words", "sentences", "paragraphs"):
            metrics_totals[key] += float(metrics.get(key, 0))
        if "dialogue_percent" in metrics:
            metrics_totals["dialogue_percent_sum"] += float(metrics["dialogue_percent"])
            metrics_totals["dialogue_documents"] += 1
        if "readability" in metrics:
            metrics_totals["readability_sum"] += float(metrics["readability"])
            metrics_totals["readability_documents"] += 1
        for finding in findings:
            all_findings.append(
                {
                    **finding,
                    "id": uuid4().hex,
                    "run_id": run_id,
                    "status": "open",
                    "path": path,
                    "binder_node_id": document["binder_node_id"] or None,
                    "source_hash": source_hash,
                    "stale": False,
                }
            )

    project_hash = _hash("\n".join(source_hashes))
    by_report = Counter(item["report_id"] for item in all_findings)
    by_severity = Counter(item["severity"] for item in all_findings)
    metrics: dict[str, float | int] = {
        "words": int(metrics_totals["words"]),
        "sentences": int(metrics_totals["sentences"]),
        "paragraphs": int(metrics_totals["paragraphs"]),
    }
    if metrics_totals["dialogue_documents"]:
        metrics["dialogue_percent"] = round(
            metrics_totals["dialogue_percent_sum"] / metrics_totals["dialogue_documents"], 2
        )
    if metrics_totals["readability_documents"]:
        metrics["readability"] = round(
            metrics_totals["readability_sum"] / metrics_totals["readability_documents"], 2
        )
    summary = {
        "by_report": dict(by_report),
        "by_severity": dict(by_severity),
        "metrics": metrics,
    }
    with _connect(slug) as con:
        con.execute(
            """
            INSERT INTO editorial_runs
            (id, created_at, scope, path, reports_json, project_hash, documents, words, findings, summary_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                created_at,
                request.scope,
                request.path,
                json.dumps(reports),
                project_hash,
                len(documents),
                total_words,
                len(all_findings),
                json.dumps(summary),
            ),
        )
        con.executemany(
            """
            INSERT INTO editorial_findings
            (id, run_id, report_id, severity, status, path, binder_node_id, start_offset, end_offset,
             line, excerpt, anchor_text, message, suggestion, source_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["id"],
                    run_id,
                    item["report_id"],
                    item["severity"],
                    item["status"],
                    item["path"],
                    item["binder_node_id"],
                    item["start_offset"],
                    item["end_offset"],
                    item["line"],
                    item["excerpt"],
                    item["anchor_text"],
                    item["message"],
                    item["suggestion"],
                    item["source_hash"],
                    created_at,
                )
                for item in all_findings
            ],
        )
    return {
        "id": run_id,
        "created_at": created_at,
        "scope": request.scope,
        "path": request.path,
        "reports": reports,
        "project_hash": project_hash,
        "documents": len(documents),
        "words": total_words,
        "findings": len(all_findings),
        "by_report": dict(by_report),
        "by_severity": dict(by_severity),
        "metrics": metrics,
        "items": all_findings,
    }


def _run_from_row(row: sqlite3.Row) -> dict[str, Any]:
    summary = json.loads(row["summary_json"])
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "scope": row["scope"],
        "path": row["path"],
        "reports": json.loads(row["reports_json"]),
        "project_hash": row["project_hash"],
        "documents": row["documents"],
        "words": row["words"],
        "findings": row["findings"],
        "by_report": summary.get("by_report", {}),
        "by_severity": summary.get("by_severity", {}),
        "metrics": summary.get("metrics", {}),
    }


def list_editorial_runs(slug: str, limit: int = 30) -> list[dict[str, Any]]:
    with _connect(slug) as con:
        rows = con.execute(
            "SELECT * FROM editorial_runs ORDER BY created_at DESC LIMIT ?",
            (max(1, min(limit, 200)),),
        ).fetchall()
    return [_run_from_row(row) for row in rows]


def _finding_from_row(slug: str, row: sqlite3.Row) -> dict[str, Any]:
    definition = REPORT_MAP.get(row["report_id"], {"name": row["report_id"], "category": "other"})
    try:
        current_hash = _hash(read_text(slug, row["path"]))
    except (FileNotFoundError, OSError, UnicodeError, ValueError):
        current_hash = ""
    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "report_id": row["report_id"],
        "report_name": definition["name"],
        "category": definition["category"],
        "severity": row["severity"],
        "status": row["status"],
        "path": row["path"],
        "binder_node_id": row["binder_node_id"],
        "start_offset": row["start_offset"],
        "end_offset": row["end_offset"],
        "line": row["line"],
        "excerpt": row["excerpt"],
        "anchor_text": row["anchor_text"],
        "message": row["message"],
        "suggestion": row["suggestion"],
        "source_hash": row["source_hash"],
        "stale": current_hash != row["source_hash"],
    }


def list_editorial_findings(
    slug: str,
    *,
    run_id: str | None = None,
    report_id: str | None = None,
    status: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    if report_id:
        if report_id not in REPORT_MAP:
            raise ValueError(f"Unknown editorial report: {report_id}")
        clauses.append("report_id = ?")
        params.append(report_id)
    if status:
        if status not in {"open", "resolved", "ignored"}:
            raise ValueError("Editorial finding status must be open, resolved, or ignored")
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(limit, 5000)))
    with _connect(slug) as con:
        rows = con.execute(
            f"SELECT * FROM editorial_findings {where} ORDER BY path, start_offset, report_id LIMIT ?",
            params,
        ).fetchall()
    return [_finding_from_row(slug, row) for row in rows]


def get_editorial_run(slug: str, run_id: str) -> dict[str, Any]:
    with _connect(slug) as con:
        row = con.execute("SELECT * FROM editorial_runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise FileNotFoundError(run_id)
    return {**_run_from_row(row), "items": list_editorial_findings(slug, run_id=run_id, limit=5000)}


def update_finding_status(slug: str, finding_id: str, status: str) -> dict[str, Any]:
    if status not in {"open", "resolved", "ignored"}:
        raise ValueError("Editorial finding status must be open, resolved, or ignored")
    with _connect(slug) as con:
        row = con.execute("SELECT * FROM editorial_findings WHERE id = ?", (finding_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(finding_id)
        con.execute("UPDATE editorial_findings SET status = ? WHERE id = ?", (status, finding_id))
        row = con.execute("SELECT * FROM editorial_findings WHERE id = ?", (finding_id,)).fetchone()
    return _finding_from_row(slug, row)
