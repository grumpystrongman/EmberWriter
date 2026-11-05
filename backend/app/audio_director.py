"""Non-destructive audiobook performance manuscript, with explicit attribution QA.

The source text is never rewritten. Every character remains in exactly one span.
Unresolved dialogue blocks production rather than silently using the narrator.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

QUOTE = re.compile(r'["“][^"”\r\n]+["”]')
VERBS = r'(?:said|asked|replied|whispered|shouted|murmured|answered|called|cried|snapped|warned|sighed|began|added|told|insisted)'
FEELINGS = {
    "fear": (r'\b(?:afraid|terrified|frightened|trembl\w*|shak\w*|panic\w*)\b', "tense, cautious"),
    "sadness": (r'\b(?:sob\w*|wept|crying|grief|mourn\w*|heartbroken)\b', "soft, weighted"),
    "joy": (r'\b(?:laugh\w*|delighted|joyful|grinn\w*|cheer\w*)\b', "warm, lifted"),
    "anger": (r'\b(?:furious|angry|snarl\w*|rage|seeth\w*)\b', "firm, clipped"),
    "urgency": (r'\b(?:urgent|hurry|quickly|rushed|shouted|yelled)\b', "brisk, urgent"),
}


def _match_name(fragment: str, names: list[str], *, before: bool) -> str | None:
    for name in names:
        escaped = re.escape(name)
        if before:
            pattern = rf'\b{escaped}\s+{VERBS}\s*[,;:]?\s*$'
        else:
            pattern = rf'^\s*[,;]?\s*{escaped}\s+{VERBS}\b'
        if re.search(pattern, fragment, re.I):
            return name
    return None


def _emotion(context: str) -> dict:
    # Conservative cue suggestions, not a claim of emotional understanding.
    matches = [name for name, (pattern, _) in FEELINGS.items()
               if re.search(pattern, context, re.I)]
    if len(matches) != 1:
        return {"emotion": "neutral", "delivery": "natural", "confidence": "low"}
    emotion = matches[0]
    return {"emotion": emotion, "delivery": FEELINGS[emotion][1],
            "confidence": "medium"}


def compile_performance(text: str, cast: dict[str, dict] | list[str],
                        overrides: dict[str, str] | None = None) -> dict:
    """Produce a lossless, editable cue sheet. Ambiguities are explicit."""
    names = sorted(cast if isinstance(cast, list) else cast.keys(), key=len, reverse=True)
    overrides = overrides or {}
    spans = []
    cursor = 0
    quotes = list(QUOTE.finditer(text))
    last_explicit = None
    for i, quote in enumerate(quotes):
        start, end = quote.span()
        if start > cursor:
            spans.append({"start": cursor, "end": start, "speaker": "Narrator",
                          "kind": "narration", "text": text[cursor:start]})
        # Only local prose between adjacent quotes; never search earlier quotes.
        left = text[max(cursor, start - 180):start]
        right_limit = quotes[i + 1].start() if i + 1 < len(quotes) else len(text)
        right = text[end:min(right_limit, end + 180)]
        explicit_left = _match_name(left, names, before=True)
        explicit_right = _match_name(right, names, before=False)
        # A tag such as 'Ivo replied, "...' introduces the NEXT quotation;
        # it is not an attribution for the immediately preceding quote.
        if i + 1 < len(quotes) and right.rstrip().endswith(','):
            explicit_right = None
        speaker = overrides.get(f"{start}:{end}")
        method = "author_override" if speaker else ""
        if not speaker and explicit_left and explicit_right and explicit_left != explicit_right:
            method = "conflict"
        elif not speaker:
            speaker = explicit_left or explicit_right
            method = "explicit" if speaker else "unresolved"
        if speaker and speaker not in names:
            raise ValueError(f"Unknown speaker override: {speaker}")
        if speaker and method == "explicit":
            last_explicit = speaker
        # Inference is advisory only; unresolved lines must be reviewed.
        context = (left[-100:] + " " + right[:100])
        cue = _emotion(context)
        spans.append({"start": start, "end": end, "kind": "dialogue",
                      "text": text[start:end], "speaker": speaker,
                      "attribution": method, "suggested_previous_speaker": last_explicit if not speaker else None,
                      "performance": cue})
        cursor = end
    if cursor < len(text):
        spans.append({"start": cursor, "end": len(text),
                      "kind": "narration", "speaker": "Narrator", "text": text[cursor:]})
    assert "".join(s["text"] for s in spans) == text
    unresolved = [s for s in spans if s["kind"] == "dialogue" and not s["speaker"]]
    return {"schema": "emberwriter.audio_performance.v1",
            "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "source_length": len(text), "spans": spans,
            "unresolved_count": len(unresolved),
            "render_ready": not unresolved,
            "warnings": [f"Unresolved dialogue at {s['start']}:{s['end']}: {s['text'][:80]}"
                         for s in unresolved]}


def validate(performance: dict, source: str, voices: dict) -> None:
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != performance.get("source_sha256"):
        raise ValueError("Performance manuscript is stale against the source")
    spans = performance["spans"]
    if "".join(s["text"] for s in spans) != source:
        raise ValueError("Performance manuscript does not preserve source verbatim")
    if performance["unresolved_count"]:
        raise ValueError(f"{performance['unresolved_count']} dialogue lines need speaker review")
    for span in spans:
        if span["speaker"] not in voices:
            raise ValueError(f"No voice assigned for {span['speaker']}")


def save_performance(path: Path, performance: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(performance, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def render_plan(performance: dict, source: str, voices: dict,
                engine: str = "kokoro") -> list[dict]:
    """Engine-independent acting directions; only validated turns can render.

    Fish cues use descriptive delivery tags. Kokoro has no equivalent native
    support; never feed its model a tag that it will read aloud.
    """
    if engine not in {"kokoro", "fish"}:
        raise ValueError("Unknown audiobook speech engine")
    validate(performance, source, voices)
    result = []
    for span in performance["spans"]:
        if not span["text"].strip():
            continue
        speaker = span["speaker"]
        profile = voices[speaker]
        if isinstance(profile, str):
            profile = {"voice_id": profile, "speed": 1.0}
        direction = span.get("performance") or {}
        text = span["text"]
        # Only engine-specific adapters may inject expressive text; the
        # canonical source and character attribution never change.
        if engine == "fish" and span["kind"] == "dialogue" and direction.get("emotion") not in (None, "neutral"):
            text = f"[{direction.get('delivery', direction['emotion'])}] {text}"
        result.append({"speaker": speaker, "source_start": span["start"],
                       "source_end": span["end"], "source_text": span["text"],
                       "tts_text": text, "voice_id": profile["voice_id"],
                       "speed": profile.get("speed", 1.0),
                       "emotion": direction.get("emotion", "neutral"),
                       "delivery": direction.get("delivery", "natural"),
                       "engine": engine})
    return result


def revise_speaker(performance: dict, start: int, end: int, speaker: str,
                   valid_characters: list[str], origin: str = "author_override") -> dict:
    """Explicit editor correction; preserves source bytes and all other cues."""
    if speaker not in valid_characters:
        raise ValueError("Cannot assign an unknown speaker")
    selected = [s for s in performance["spans"]
                if s["start"] == start and s["end"] == end and s["kind"] == "dialogue"]
    if len(selected) != 1:
        raise ValueError("No dialogue line at that source range")
    selected[0]["speaker"] = speaker
    if origin not in {"author_override", "editor_suggestion"}:
        raise ValueError("Unrecognized speaker decision origin")
    selected[0]["attribution"] = origin
    selected[0]["suggested_previous_speaker"] = None
    unresolved = [s for s in performance["spans"]
                  if s["kind"] == "dialogue" and not s["speaker"]]
    performance["unresolved_count"] = len(unresolved)
    performance["render_ready"] = not unresolved
    performance["warnings"] = [
        f"Unresolved dialogue at {s['start']}:{s['end']}: {s['text'][:80]}"
        for s in unresolved]
    return performance


def load_or_compile(path: Path, source: str, names: list[str],
                    casts: list[dict] | None = None) -> dict:
    """Refresh detections, retain source-matching author decisions and cues."""
    overrides = {}
    for cast in casts or []:
        start, end = cast["start"], cast["end"]
        if not (0 <= start < end <= len(source)) or source[start:end] != cast["text"]:
            raise ValueError("An existing dialogue cast is stale")
        overrides[f"{start}:{end}"] = cast["character"]
    old = {}
    if path.is_file():
        candidate = json.loads(path.read_text(encoding="utf-8"))
        if candidate.get("source_sha256") == hashlib.sha256(source.encode("utf-8")).hexdigest():
            old = {(s["start"], s["end"]): s for s in candidate.get("spans", [])
                   if s.get("kind") == "dialogue"}
            for (start, end), row in old.items():
                if row.get("attribution") in {"author_override", "editor_suggestion"} and row.get("speaker"):
                    overrides.setdefault(f"{start}:{end}", row["speaker"])
    result = compile_performance(source, names, overrides)
    for row in result["spans"]:
        if row["kind"] != "dialogue":
            continue
        previous = old.get((row["start"], row["end"]))
        if (previous and previous.get("attribution") == "editor_suggestion"
                and row["speaker"] == previous.get("speaker")):
            row["attribution"] = "editor_suggestion"
        if previous and previous.get("text") == row["text"] and isinstance(previous.get("performance"), dict):
            row["performance"] = previous["performance"]
    save_performance(path, result)
    return result


def revise_direction(performance: dict, start: int, end: int,
                     emotion: str, delivery: str) -> dict:
    if not re.fullmatch(r"[a-z][a-z -]{0,39}", emotion):
        raise ValueError("Invalid emotion label")
    if not 1 <= len(delivery) <= 140 or any(c in delivery for c in "<>[]\r\n"):
        raise ValueError("Performance direction must be plain text of 1–140 characters")
    matches = [s for s in performance["spans"]
               if s["start"] == start and s["end"] == end and s["kind"] == "dialogue"]
    if len(matches) != 1:
        raise ValueError("Dialogue selection does not match current manuscript")
    matches[0]["performance"] = {"emotion": emotion, "delivery": delivery,
                                 "confidence": "author_directed"}
    return performance
