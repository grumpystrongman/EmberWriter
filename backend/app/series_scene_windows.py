"""Deterministic reading windows and tentative, source-bound literary cues.

Only verified EPUB headings and explicit typography are structural evidence.
Length-based splits are navigation conveniences, not narrative scene boundaries.
Suggestions are not author-approved scenes or canon. No manuscript bytes stored.
"""
from __future__ import annotations

import hashlib
import re

from . import series_canon as canon
from . import series_epub_index as epub_index
from . import series_vault as vault

WINDOW_TARGET = 5200
WINDOW_LIMIT = 8500
MAX_PER_BOOK = 1200
MAX_BOOK_CHARS = 2_000_000
BREAK = re.compile(r"(?m)^[ \t]*(?:\*\s*\*\s*\*|#\s*#\s*#|\u2042|\u2014\s*\u2014\s*\u2014)[ \t]*$")
PARAGRAPH = re.compile(r"\n\s*\n")
MAX_QUOTE = 250


def _sections(text: str, saved: dict | None) -> list[dict]:
    if not saved:
        return [{"start": 0, "end": len(text), "title": "Unindexed source",
                 "section_index": None, "verified": False}]
    ordered = sorted(saved["sections"], key=lambda item: (item["start"], item["end"]))
    spans = []
    last = 0
    for section in ordered:
        if section["start"] < last:
            # Valid original metadata can contain nested chapter headings.
            # Only emit one contiguous sequence, not overlapping excerpts.
            continue
        if section["start"] > last and text[last:section["start"]].strip():
            spans.append({"start": last, "end": section["start"], "title": "Between EPUB sections",
                          "section_index": None, "verified": False})
        spans.append({"start": section["start"], "end": section["end"],
                      "title": section["title"], "section_index": section["index"],
                      "verified": True})
        last = section["end"]
    if last < len(text) and text[last:].strip():
        spans.append({"start": last, "end": len(text), "title": "After EPUB sections",
                      "section_index": None, "verified": False})
    return spans


def _windows(text: str, start: int, end: int):
    points = [start]
    # Typographic separators are explicit textual evidence of a boundary,
    # but the author still decides whether it signifies a new scene.
    explicit = [(match.start(), match.end()) for match in BREAK.finditer(text, start, end)
                if start < match.start() < match.end() < end]
    for marker_start, marker_end in explicit:
        if marker_start > points[-1]:
            points.append(marker_start)
        points.append(marker_end)
    points.append(end)
    for index in range(len(points)-1):
        a, b = points[index:index+2]
        if b <= a or not text[a:b].strip():
            continue
        if index % 2 == 1 and explicit:
            # The literal separator itself is not a narrative excerpt.
            continue
        cursor = a
        while cursor < b:
            if b-cursor <= WINDOW_LIMIT:
                final = b
            else:
                bound = min(b, cursor+WINDOW_TARGET)
                candidates = [m.end() for m in PARAGRAPH.finditer(text, cursor, min(b, cursor+WINDOW_LIMIT))
                              if cursor + WINDOW_TARGET//2 <= m.end() <= cursor+WINDOW_LIMIT]
                final = min(candidates, key=lambda x: abs(x-bound)) if candidates else min(b,cursor+WINDOW_TARGET)
            if final <= cursor:
                raise RuntimeError("Scene window scanner did not advance")
            if text[cursor:final].strip():
                yield cursor, final, ("length_limited_reading_window" if final < b or cursor > a
                                     else "section_or_typographic_span")
            cursor = final


# These cues are intentionally narrow. They identify review candidates, not facts.
_TIME_SHIFT = re.compile(
    r"(?i)(?:\w+\s+)?(?:days?|weeks?|months?|years?)\s+(?:later|earlier)\b"
)
_FIRST_PERSON = re.compile(r"(?i)\b(?:I|me|my|mine|myself)\b")
_QUOTED = re.compile(r'"[^"\n]*(?:"|$)|\u201c[^\u201d\n]*(?:\u201d|$)')


def scene_suggestions(text: str, start: int = 0, end: int | None = None) -> list[dict]:
    """Return source offsets and literal evidence for tentative boundaries only."""
    end = len(text) if end is None else end
    suggestions = []
    for match in BREAK.finditer(text, start, end):
        before = text[start:match.start()].rstrip()
        after = match.end()
        while after < end and text[after].isspace():
            after += 1
        # A mark introduced as displayed content is weak boundary evidence.
        if before and after < end and not before.endswith((':', '\uff1a')):
            suggestions.append({"offset": after, "status": "heuristic_suggestion", "reason": "typographic_separator",
                                "evidence_start": match.start(), "evidence_end": match.end()})
    for match in PARAGRAPH.finditer(text, start, end):
        after = match.end()
        cue = _TIME_SHIFT.match(text, after, end)
        if start < match.start() and after < end and cue:
            suggestions.append({"offset": after, "status": "heuristic_suggestion", "reason": "elapsed_time_cue",
                                "evidence_start": after, "evidence_end": cue.end()})
    return sorted(suggestions, key=lambda item: item["offset"])


def pov_suggestion(text: str) -> dict:
    """Suggest first person only with repeated unquoted first-person signals.

    Quoted speech is ignored; this remains a fallible voice cue, not a claim
    about a particular character or an author-approved viewpoint.
    """
    unquoted = _QUOTED.sub(lambda m: ' ' * len(m.group()), text)
    hits = list(_FIRST_PERSON.finditer(unquoted))
    if len(hits) >= 2:
        return {"style": "first_person", "offset_basis": "window", "evidence": [
            {"start": m.start(), "end": m.end()} for m in hits[:10]],
            "status": "heuristic_suggestion"}
    return {"style": "undetermined", "evidence": [], "status": "abstained"}



# These patterns label language in a sentence, not the truth of its content.
_SENTENCE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")
_MENTAL = re.compile(
    r"\b(?P<subject>[A-Z][a-z]+)\s+(?P<verb>believed|thought|suspected|"
    r"wondered|knew|learned|realized|remembered)\b"
)
_CONTEXT = (
    ("dream", re.compile(r"\b(?:dream|dreamed|dreamt|dreaming)\b", re.I)),
    ("flashback", re.compile(r"\b(?:years? earlier|months? earlier|weeks? earlier|"
                             r"remembered|recalled)\b", re.I)),
    ("hearsay", re.compile(r"\b(?:heard|rumou?r|told|said|claimed)\b", re.I)),
    ("reader_revelation", re.compile(r"\b(?:the narrator (?:explained|revealed)|"
                                     r"unbeknownst to)\b", re.I)),
)



def narrative_context_cues(text: str) -> list[dict]:
    """Return literal context markers, without claiming their scope or truth."""
    cues = [{"category": "quoted_dialogue", "start": m.start(), "end": m.end()}
            for m in _QUOTED.finditer(text)]
    for category, pattern in _CONTEXT:
        for match in pattern.finditer(text):
            # A marker inside speech describes speech, not narrative context.
            if any(q["start"] <= match.start() < q["end"] for q in cues
                   if q["category"] == "quoted_dialogue"):
                continue
            cues.append({"category": category, "start": match.start(), "end": match.end()})
    return [dict(cue, offset_basis="window", status="heuristic_suggestion")
            for cue in sorted(cues, key=lambda item: item["start"])[:50]]


def knowledge_suggestions(text: str) -> list[dict]:
    """Identify literal mental-state language for human review, never facts.

    Offsets are relative to the supplied window. Context labels describe lexical
    cues in the same sentence, not proven narrative boundaries or truth.
    """
    quoted = list(_QUOTED.finditer(text))
    results = []
    for sentence in _SENTENCE.finditer(text):
        body = sentence.group()
        contexts = [label for label, pattern in _CONTEXT if pattern.search(body)]
        for match in _MENTAL.finditer(text, sentence.start(), sentence.end()):
            # A quote or an ambiguous unclosed quote cannot establish a narrator's
            # attribution; reported speech is also kept distinct from belief.
            if any(q.start() <= match.start() < q.end() for q in quoted):
                continue
            if "hearsay" in contexts:
                continue
            verb = match.group("verb").lower()
            results.append({
                "subject_literal": match.group("subject"),
                "cue": verb,
                "category": "character_belief" if verb in {
                    "believed", "thought", "suspected", "wondered"
                } else "character_knowledge_claim",
                "contexts": contexts or ["narration"],
                "evidence": {"start": sentence.start(), "end": sentence.end()},
                "cue_start": match.start(), "cue_end": match.end(),
                "offset_basis": "window", "status": "heuristic_suggestion",
                "truth_asserted": False, "canon_asserted": False,
            })
            if len(results) >= 20:
                return results
    return results


def _people(content: str, entities: list[dict]) -> list[dict]:
    names = []
    for entity in entities:
        forms = [entity["name"], *entity.get("aliases", [])]
        found = [form for form in forms if len(form.strip())>=2
                 and re.search(r"(?<!\w)"+re.escape(form.strip())+r"(?!\w)", content, re.IGNORECASE)]
        if found:
            names.append({"entity_id": entity["id"], "name": entity["name"],
                          "literal_form": found[0]})
        if len(names)>=10:
            break
    return names


def scan(series_id: str, *, book: int, offset: int = 0, limit: int = 40) -> dict:
    if not 1 <= book <= 9999 or not 0 <= offset <= 100000 or not 1 <= limit <= 100:
        raise ValueError("Invalid reading-window scan bounds")
    details = vault.series_detail(series_id)
    volumes = [v for v in details["volumes"] if v["ordinal"] == book]
    if not volumes:
        return {"book":book,"total":0,"windows":[],"source_count":0,
                "truncated":False,"auto_scene_approved":False}
    people = [e for e in canon.list_entities(series_id) if e["kind"]=="character"]
    rows = []
    count_chars = 0
    truncated = False
    for source in volumes[0]["sources"]:
        record, text = vault.source_text(series_id, source["id"])
        count_chars += len(text)
        if count_chars > MAX_BOOK_CHARS:
            truncated=True
            break
        saved = epub_index.read(series_id, source["id"])
        for section in _sections(text, saved):
            suggestions = scene_suggestions(text, section["start"], section["end"])
            for start, end, reason in _windows(text, section["start"], section["end"]):
                if len(rows)>=MAX_PER_BOOK:
                    truncated=True
                    break
                segment = text[start:end]
                structural = section["verified"]
                rows.append({
                    "source_id": source["id"], "source_hash": record["sha256"],
                    "book":book, "start":start, "end":end, "length":end-start,
                    "range_hash": hashlib.sha256(segment.encode("utf8")).hexdigest(),
                    "section_title": section["title"], "section_index": section["section_index"],
                    "confirmed_epub_structure":structural,
                    "boundary_kind":reason if reason=="length_limited_reading_window"
                                    else ("verified_epub_section" if structural else "source_span"),
                    "preview":segment[:MAX_QUOTE].strip(),
                    "character_mentions":_people(segment, people),
                    "scene_confirmed":False, "pov_inferred":False,
                    "reading_window_only":True,
                    "scene_boundary_suggestions": [
                        item for item in suggestions
                        if start <= item["offset"] < end],
                    "pov_suggestion": pov_suggestion(segment),
                    "knowledge_suggestions": knowledge_suggestions(segment),
                    "narrative_context_cues": narrative_context_cues(segment),
                })
            if truncated:
                break
        if truncated:
            break
    return {"series_id":series_id,"book":book,"total":len(rows),
            "windows":rows[offset:offset+limit],
            "source_count":len(volumes[0]["sources"]),
            "truncated":truncated,"auto_scene_approved":False,
            "disclaimer":(
                "EPUB section boundaries are verified formatting, not necessarily scenes. "
                "Other divisions are bounded reading windows. Character names are literal "
                "text matches only. No interaction, scene, character knowledge, "
                "or canon is asserted. Boundary, POV, and knowledge cues are fallible and require author review."
            )}


def detail(series_id: str, *, book:int, source_id:str, start:int, end:int) -> dict:
    if start<0 or end<=start or end-start>WINDOW_LIMIT:
        raise ValueError("Invalid window coordinate bounds")
    source, text = vault.source_text(series_id, source_id)
    if source["ordinal"] != book:
        raise FileNotFoundError("Window does not belong to requested book")
    saved = epub_index.read(series_id, source_id)
    valid = any(a==start and b==end for section in _sections(text, saved)
                for a,b,_ in _windows(text, section["start"], section["end"]))
    if not valid:
        raise ValueError("Window is not a valid source-verified reading segment")
    segment = text[start:end]
    return {"source_id":source_id,"book":book,"start":start,"end":end,
            "range_hash":hashlib.sha256(segment.encode("utf8")).hexdigest(),"text":segment,
            "source_verified":True,"scene_confirmed":False}
