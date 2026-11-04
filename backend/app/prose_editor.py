"""Offline sentence-level prose fixes and cautious POV/tense observations.

All suggestions are transparent regular-expression heuristics, NOT a
comprehensive grammar engine. Fixes use exact source-version and offset checks
and preserve native project snapshots before editing. Every action is optional.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .manuscript_intelligence import _chapters
from .storage import get_project, project_root, read_text, save_text
from .book_studio import edit_candidate, candidate, load_state

MAX_BYTES = 1_000_000
MAX_FINDINGS = 220
WORDS = re.compile(r"\b[A-Za-z]+(?:'[A-Za-z]+)?\b")
DOUBLE = re.compile(r"\b([A-Za-z]{2,})[ \t]+\1\b", re.I)
COULD_OF = re.compile(r"\b(could|would|should|must|might)[ \t]+of\b", re.I)
# Unambiguous common typos only. In-world names and unusual diction can be dismissed.
COMMON_TYPOS = {
    "alot": "a lot", "definately": "definitely", "seperate": "separate",
    "recieve": "receive", "occured": "occurred", "untill": "until",
    "writting": "writing", "becuase": "because", "wich": "which",
}
TYPO = re.compile(r"\b(?:" + "|".join(COMMON_TYPOS) + r")\b", re.I)
SPACE_BEFORE = re.compile(r"(?<=\w)[ \t]+(?=[,.!?;:])")
DOUBLE_SPACES = re.compile(r"(?<=\S)[ \t]{2,}(?=\S)")
WEAK = re.compile(r"\b(?:due to the fact that|in order to|at this point in time|very unique)\b", re.I)
FIRST_PERSON = re.compile(r"\b(?:I|me|my|mine|myself|we|us|our|ours)\b")
SECOND_PERSON = re.compile(r"\b(?:you|your|yours|yourself|yourselves)\b", re.I)
PAST = re.compile(r"\b(?:walked|looked|turned|said|asked|thought|went|saw|felt|knew|was|were|had|did|stood|ran)\b", re.I)
PRESENT = re.compile(r"\b(?:walks|looks|turns|says|asks|thinks|goes|sees|feels|knows|is|are|has|does|stands|runs)\b", re.I)
QUOTES = re.compile(r'["“][^"”\n]*["”]')
RULES = {
    "double_word": "Possible duplicated word",
    "lexical_typo": "Possible spelling typo",
    "modal_of": "Possible incorrect modal construction",
    "space_punctuation": "Unexpected space before punctuation",
    "double_space": "Extra spaces within a sentence",
    "wordiness": "Potentially wordy expression",
    "pov": "Possible point-of-view shift in narration",
    "tense": "Possible tense shift in narration",
}
REPLACEMENTS = {
    "due to the fact that": "because", "in order to": "to",
    "at this point in time": "now", "very unique": "unique",
}


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _path(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "prose-editor-decisions.json"


def _load(slug: str) -> dict:
    file = _path(slug)
    if not file.is_file():
        return {}
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or len(data) > 1000:
        raise ValueError("Prose editor decisions are invalid")
    return data


def _write(slug: str, data: dict):
    dest = _path(slug)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(dest)


def sources(slug: str) -> list[dict]:
    return [{"path": ch["path"], "title": ch["title"], "status": ch["status"]}
            for ch in _chapters(slug)][:140]


def _get(slug: str, path: str) -> tuple[str, str]:
    available = {item["path"]: item for item in sources(slug)}
    if path not in available:
        raise FileNotFoundError("Chapter is not in this manuscript")
    if path.startswith("book-studio:candidate:"):
        number = int(path.rsplit(":", 1)[1])
        state = load_state(slug)
        if state["chapters"][number - 1]["status"] != "candidate":
            raise ValueError("Only unapproved candidates can be edited")
        text = candidate(slug, number)["content"]
    else:
        text = read_text(slug, path)
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Chapter exceeds 1 MB editing limit")
    return text, available[path]["status"]


def _fix_case(before: str, suggested: str) -> str:
    if before.isupper():
        return suggested.upper()
    if before[0].isupper():
        return suggested[0].upper() + suggested[1:]
    return suggested


def analyze(slug: str, path: str, perspective: str = "unspecified",
            tense: str = "unspecified") -> dict:
    text, status = _get(slug, path)
    return analyze_text(slug, path, text, status, perspective, tense)


def analyze_text(slug: str, path: str, text: str, status: str,
                 perspective: str = "unspecified", tense: str = "unspecified") -> dict:
    """Scan already-loaded chapter text, avoiding redundant whole-book reads."""
    if perspective not in ("unspecified", "first", "third") or tense not in ("unspecified", "past", "present"):
        raise ValueError("Invalid narrative point of view or tense")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Chapter exceeds 1 MB editing limit")
    fingerprint = _hash(text)
    decisions = _load(slug)
    rows = []
    lines = text.splitlines(keepends=True)
    location = 0

    def emit(rule: str, begin: int, end: int, suggested: str | None = None, why: str = ""):
        if len(rows) >= MAX_FINDINGS:
            return
        selected = text[begin:end]
        if not selected or len(selected) > 320:
            return
        identifier = _hash("|".join([path, fingerprint, rule, str(begin), selected]))[:24]
        existing = decisions.get(identifier, {})
        rows.append({
            "id": identifier, "rule": rule, "title": RULES[rule],
            "start": begin, "end": end, "matched": selected,
            "suggested": suggested, "why": why or RULES[rule],
            "line": text.count("\n", 0, begin) + 1,
            "excerpt": text[max(0, begin - 65):min(len(text), end + 85)].replace("\n", " ").strip(),
            "decision": existing.get("decision", "pending"),
            "reason": existing.get("reason", ""),
        })

    for line in lines:
        line_start = location
        location += len(line)
        # Dialogue is excluded from narrative POV and tense flags.
        stripped = QUOTES.sub(lambda m: " " * len(m.group()), line)
        for m in DOUBLE.finditer(line):
            emit("double_word", line_start + m.start(), line_start + m.end(),
                 m.group(1), "A word repeats consecutively; check for intentional emphasis.")
        for m in TYPO.finditer(line):
            emit("lexical_typo", line_start + m.start(), line_start + m.end(),
                 _fix_case(m.group(), COMMON_TYPOS[m.group().casefold()]),
                 "Common English typo; confirm whether the original is intentional dialogue or in-world terminology.")
        for m in COULD_OF.finditer(line):
            emit("modal_of", line_start + m.start(), line_start + m.end(),
                 _fix_case(m.group(0), m.group(1) + " have"),
                 "A modal verb normally takes 'have' rather than 'of'.")
        for m in SPACE_BEFORE.finditer(line):
            emit("space_punctuation", line_start + m.start(), line_start + m.end(),
                 "", "Remove the gap immediately before this punctuation mark.")
        if not line.lstrip().startswith(("#", ">", "*", "-", "|")):
            for m in DOUBLE_SPACES.finditer(line):
                emit("double_space", line_start + m.start(), line_start + m.end(),
                     " ", "Multiple spaces appear between words.")
        for m in WEAK.finditer(stripped):
            phrase = m.group().casefold()
            emit("wordiness", line_start + m.start(), line_start + m.end(),
                 _fix_case(m.group(), REPLACEMENTS[phrase]),
                 "Optional concise wording; the original may fit your voice better.")
        if not line.lstrip().startswith(("#", ">", "*", "-", "|")):
            narrative_words = len(WORDS.findall(stripped))
            if narrative_words >= 12:
                if perspective == "third":
                    for m in FIRST_PERSON.finditer(stripped):
                        emit("pov", line_start + m.start(), line_start + m.end(),
                             why="First-person marker appears outside quotation marks in a third-person chapter. First-person thoughts may be intentional.")
                elif perspective == "first":
                    # Don't flag ordinary 'you' in free indirect thought or second-person address.
                    if len(SECOND_PERSON.findall(stripped)) >= 3:
                        m = SECOND_PERSON.search(stripped)
                        if m:
                            emit("pov", line_start + m.start(), line_start + m.end(),
                                 why="Repeated second-person forms in first-person narration deserve a POV check.")
                past, present = list(PAST.finditer(stripped)), list(PRESENT.finditer(stripped))
                if tense == "past" and len(present) >= 3 and len(present) > len(past) * 2:
                    m = present[0]
                    emit("tense", line_start + m.start(), line_start + m.end(),
                         why="Several present-tense verbs appear in a predominantly past-tense chapter; dialogue, memories or stylistic shifts may explain them.")
                elif tense == "present" and len(past) >= 3 and len(past) > len(present) * 2:
                    m = past[0]
                    emit("tense", line_start + m.start(), line_start + m.end(),
                         why="Several past-tense verbs appear in a present-tense chapter; flashbacks and backstory may be intentional.")

    return {
        "path": path, "status": status, "source_hash": fingerprint,
        "perspective": perspective, "tense": tense, "findings": rows,
        "outstanding": sum(r["decision"] == "pending" for r in rows),
        "dismissed": sum(r["decision"] == "dismissed" for r in rows),
        "truncated": len(rows) >= MAX_FINDINGS,
        "method": "Offline pattern-based grammar suggestions and optional, low-confidence narration warnings. No external grammar engine or definitive POV/tense certification.",
    }


def decide(slug: str, path: str, finding_id: str, source_hash: str,
           action: str, perspective: str = "unspecified", tense: str = "unspecified",
           reason: str = "") -> dict:
    if action not in ("dismiss", "reopen", "apply"):
        raise ValueError("Action must be dismiss, reopen, or apply")
    report = analyze(slug, path, perspective, tense)
    if source_hash != report["source_hash"]:
        raise ValueError("Chapter was edited since inspection; rescan before acting")
    finding = next((f for f in report["findings"] if f["id"] == finding_id), None)
    if finding is None:
        raise FileNotFoundError("Finding is not in the current chapter")
    decisions = _load(slug)
    if action == "apply":
        replacement = finding["suggested"]
        if replacement is None:
            raise ValueError("This is a subjective observation; edit the prose yourself")
        original, _ = _get(slug, path)
        if original[finding["start"]:finding["end"]] != finding["matched"] or _hash(original) != source_hash:
            raise ValueError("Source changed before correction could be applied")
        edited = original[:finding["start"]] + replacement + original[finding["end"]:]
        if path.startswith("book-studio:candidate:"):
            number = int(path.rsplit(":", 1)[1])
            edit_candidate(slug, number, edited)
        else:
            # save_text creates a restorable project snapshot of the original.
            save_text(slug, path, edited)
        return {"applied": True, "snapshot_created": True, **analyze(slug, path, perspective, tense)}
    if action == "dismiss" and not 8 <= len(reason.strip()) <= 500:
        raise ValueError("A dismissal needs an 8–500 character author rationale")
    if action == "reopen":
        if finding_id not in decisions:
            raise ValueError("Finding is not currently dismissed")
        decisions.pop(finding_id)
    else:
        decisions[finding_id] = {"decision": "dismissed", "reason": reason.strip(),
                                 "recorded_at": datetime.now(timezone.utc).isoformat()}
    if len(decisions) > 1000:
        raise ValueError("Too many editorial dismissal records")
    _write(slug, decisions)
    return analyze(slug, path, perspective, tense)
