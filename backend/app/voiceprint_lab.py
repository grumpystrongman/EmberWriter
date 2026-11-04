"""Offline writing-style comparison against an author-selected reference.

No model calls, no writing modifications. Stylistic differences are described,
not scored as correctness or literary quality. Baseline remains inside project.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from statistics import mean, pstdev

from .manuscript_intelligence import _chapters
from .storage import get_project, project_root, read_text

MAX_SOURCE = 1_000_000
WORD = re.compile(r"\b[A-Za-z][A-Za-z'’-]*\b")
SENTENCE = re.compile(r"(?<=[.!?])\s+")
DIALOGUE = re.compile(r'["“][^"”\n]{3,}["”]')


def _file(slug: str) -> Path:
    get_project(slug)
    return project_root(slug) / ".ember" / "voiceprint.json"


def options(slug: str) -> list[dict]:
    files = get_project(slug)["files"]
    return [{"path": path} for path in sorted(files) if
            path.startswith(("style/", "manuscript/")) and
            path.lower().endswith((".md", ".txt")) and
            not Path(path).name.lower().startswith("readme")][:250]


def baseline(slug: str) -> dict:
    path = _file(slug)
    if not path.is_file():
        return {"selected": False, "path": ""}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("path"), str):
        raise ValueError("Voiceprint baseline selection is invalid")
    if data["path"] not in {item["path"] for item in options(slug)}:
        return {"selected": False, "path": "", "missing": True}
    return {"selected": True, "path": data["path"]}


def select(slug: str, path: str) -> dict:
    if path not in {item["path"] for item in options(slug)}:
        raise ValueError("Select a style or manuscript reference from this project")
    content = read_text(slug, path)
    if not 120 <= len(WORD.findall(content)) or len(content.encode("utf-8")) > MAX_SOURCE:
        raise ValueError("Style reference needs at least 120 words and must be under 1 MB")
    target = _file(slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.with_suffix(".json.tmp")
    stage.write_text(json.dumps({"path": path}, indent=2), encoding="utf-8")
    stage.replace(target)
    return baseline(slug)


def _fingerprint(text: str) -> dict:
    clean = re.sub(r"(?m)^#{1,6}\s+", "", text).strip()
    words = WORD.findall(clean)
    sentences = [len(WORD.findall(part)) for part in SENTENCE.split(clean)
                 if len(WORD.findall(part)) >= 2]
    paragraphs = [len(WORD.findall(part)) for part in re.split(r"\n\s*\n", clean)
                  if len(WORD.findall(part)) >= 2]
    dialogue = DIALOGUE.findall(clean)
    dialogue_words = sum(len(WORD.findall(item)) for item in dialogue)
    paragraph_mean = mean(paragraphs) if paragraphs else 0
    return {
        "words": len(words),
        "sentence_words": round(mean(sentences), 1) if sentences else 0,
        "sentence_variation": round(pstdev(sentences), 1) if len(sentences) > 1 else 0,
        "paragraph_words": round(paragraph_mean, 1),
        "dialogue_share": round(dialogue_words / max(1, len(words)), 3),
        "em_dashes_per_1000": round(clean.count("—") / max(1, len(words)) * 1000, 1),
        "questions_per_1000": round(clean.count("?") / max(1, len(words)) * 1000, 1),
        "exclamations_per_1000": round(clean.count("!") / max(1, len(words)) * 1000, 1),
        "line_count": len(clean.splitlines()),
    }


def report(slug: str) -> dict:
    choice = baseline(slug)
    if not choice.get("selected"):
        return {"configured": False, "baseline": choice, "chapters": [],
                "limitations": "Choose a reference excerpt written in your preferred voice."}
    content = read_text(slug, choice["path"])
    if len(content.encode("utf-8")) > MAX_SOURCE:
        raise ValueError("Style reference exceeds 1 MB")
    reference = _fingerprint(content)
    if reference["words"] < 120:
        return {"configured": False, "baseline": {"selected": False, "path": choice["path"], "too_short": True},
                "chapters": [], "limitations": "The reference was shortened; supply at least 120 words."}
    dimensions = {
        "sentence_words": ("Average sentence length", 0.4),
        "sentence_variation": ("Sentence length variation", 0.55),
        "paragraph_words": ("Average paragraph length", 0.55),
        "dialogue_share": ("Dialogue proportion", 0.18),
    }
    chapters = []
    for ch in _chapters(slug):
        if len(ch["text"].encode("utf-8")) > MAX_SOURCE:
            raise ValueError("A manuscript chapter exceeds 1 MB")
        result = _fingerprint(ch["text"])
        signals = []
        if result["words"] >= 75:
            for metric, (label, tolerance) in dimensions.items():
                original, current = reference[metric], result[metric]
                delta = abs(current - original)
                # Dialogue share is an absolute fraction; other dimensions
                # use relative difference. These are suggestions, not mistakes.
                change = delta if metric == "dialogue_share" else delta / max(1.0, original)
                if change >= tolerance:
                    signals.append({
                        "metric": metric, "label": label, "reference": original,
                        "chapter": current, "message": (
                            "This chapter differs noticeably from your chosen sample "
                            f"in {label.lower()}. Decide whether this suits its POV and dramatic purpose."
                        ),
                    })
        chapters.append({
            "path": ch["path"], "title": ch["title"], "status": ch["status"],
            "metrics": result, "signals": signals,
            "fingerprint": hashlib.sha256(ch["text"].encode("utf-8")).hexdigest()[:16],
        })
    return {
        "configured": True, "baseline": choice,
        "baseline_fingerprint": hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
        "reference": reference, "chapters": chapters,
        "limitations": (
            "Quantitative rhythm/proportion comparison only. Different scenes, genres, "
            "dialogue needs, manuscript lengths and POVs can legitimately differ. "
            "This is not author-identity detection, plagiarism detection, an AI detector "
            "or a literary-quality score."
        ),
    }
