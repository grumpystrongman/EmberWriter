from __future__ import annotations

import json
import re
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any

from .storage import project_root, read_text, save_text

STYLE_FIDELITY_PATH = "style/style-fidelity.json"


@dataclass(frozen=True)
class StyleMetrics:
    avg_sentence_words: float
    sentence_stddev: float
    short_sentence_ratio: float
    long_sentence_ratio: float
    avg_paragraph_words: float
    dialogue_ratio: float
    fragment_ratio: float
    exclamation_rate: float
    question_rate: float
    semicolon_rate: float
    em_dash_rate: float


def _words(text: str) -> list[str]:
    return re.findall(r"\b[\w'’-]+\b", text)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])(?:[\"'”’)]*)\s+", text) if part.strip()]


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


def measure_style(text: str) -> StyleMetrics:
    sentences = _sentences(text)
    sentence_lengths = [len(_words(sentence)) for sentence in sentences if _words(sentence)]
    paragraphs = _paragraphs(text)
    paragraph_lengths = [len(_words(paragraph)) for paragraph in paragraphs if _words(paragraph)]
    total_words = max(1, len(_words(text)))
    dialogue_words = sum(len(_words(match)) for match in re.findall(r'[“"]([^”"]+)[”"]', text))
    fragments = [
        sentence
        for sentence in sentences
        if len(_words(sentence)) <= 4
        and not re.search(
            r"\b(is|are|was|were|be|been|am|do|did|does|have|has|had|can|could|will|would|shall|should|may|might|must)\b",
            sentence,
            re.IGNORECASE,
        )
    ]
    return StyleMetrics(
        avg_sentence_words=round(mean(sentence_lengths), 2) if sentence_lengths else 0.0,
        sentence_stddev=round(pstdev(sentence_lengths), 2) if len(sentence_lengths) > 1 else 0.0,
        short_sentence_ratio=round(sum(length <= 8 for length in sentence_lengths) / max(1, len(sentence_lengths)), 3),
        long_sentence_ratio=round(sum(length >= 25 for length in sentence_lengths) / max(1, len(sentence_lengths)), 3),
        avg_paragraph_words=round(mean(paragraph_lengths), 2) if paragraph_lengths else 0.0,
        dialogue_ratio=round(dialogue_words / total_words, 3),
        fragment_ratio=round(len(fragments) / max(1, len(sentences)), 3),
        exclamation_rate=round(text.count("!") / total_words * 1000, 2),
        question_rate=round(text.count("?") / total_words * 1000, 2),
        semicolon_rate=round(text.count(";") / total_words * 1000, 2),
        em_dash_rate=round(text.count("—") / total_words * 1000, 2),
    )


def _require_project(slug: str) -> None:
    if not (project_root(slug) / "project.json").exists():
        raise FileNotFoundError(slug)


def get_style_fidelity(slug: str) -> dict[str, Any] | None:
    _require_project(slug)
    try:
        raw = read_text(slug, STYLE_FIDELITY_PATH)
    except (FileNotFoundError, OSError, ValueError):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def save_style_fidelity(slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    _require_project(slug)
    normalized = {
        "schema_version": 1,
        "metrics": dict(payload.get("metrics") or {}),
        "human_irregularities": [str(item).strip() for item in payload.get("human_irregularities", []) if str(item).strip()][:40],
        "anti_ai_rules": [str(item).strip() for item in payload.get("anti_ai_rules", []) if str(item).strip()][:60],
        "dialogue_rules": [str(item).strip() for item in payload.get("dialogue_rules", []) if str(item).strip()][:40],
        "interiority_rules": [str(item).strip() for item in payload.get("interiority_rules", []) if str(item).strip()][:40],
        "author_notes": str(payload.get("author_notes", "")).strip()[:12000],
    }
    save_text(slug, STYLE_FIDELITY_PATH, json.dumps(normalized, indent=2, ensure_ascii=False))
    return normalized


def build_style_fidelity_from_sample(slug: str, sample: str, analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    measured = measure_style(sample)
    base = analysis or {}
    payload = {
        "metrics": measured.__dict__,
        "human_irregularities": base.get("human_irregularities", []),
        "anti_ai_rules": base.get("anti_ai_rules", []),
        "dialogue_rules": base.get("dialogue_rules", []),
        "interiority_rules": base.get("interiority_rules", []),
        "author_notes": base.get("author_notes", ""),
    }
    return save_style_fidelity(slug, payload)


def build_style_fidelity_context(slug: str) -> str:
    payload = get_style_fidelity(slug)
    if not payload:
        return ""
    metrics = payload.get("metrics") or {}
    lines = [
        "## Style fidelity targets",
        "Treat these as tendencies, not rigid quotas. Preserve useful irregularity instead of mechanically hitting numbers.",
    ]
    if metrics:
        lines.append(
            "Measured manuscript tendencies: "
            f"avg sentence {metrics.get('avg_sentence_words', 0)} words; "
            f"sentence variation {metrics.get('sentence_stddev', 0)}; "
            f"short-sentence ratio {metrics.get('short_sentence_ratio', 0)}; "
            f"long-sentence ratio {metrics.get('long_sentence_ratio', 0)}; "
            f"avg paragraph {metrics.get('avg_paragraph_words', 0)} words; "
            f"dialogue ratio {metrics.get('dialogue_ratio', 0)}; "
            f"fragment ratio {metrics.get('fragment_ratio', 0)}."
        )
    for label, key in (
        ("Human irregularities to preserve", "human_irregularities"),
        ("AI tells to avoid", "anti_ai_rules"),
        ("Dialogue behavior", "dialogue_rules"),
        ("Interiority behavior", "interiority_rules"),
    ):
        values = payload.get(key) or []
        if values:
            lines.append(label + ":")
            lines.extend(f"- {item}" for item in values)
    if payload.get("author_notes"):
        lines.extend(["Author overrides:", str(payload["author_notes"])])
    return "\n".join(lines)
