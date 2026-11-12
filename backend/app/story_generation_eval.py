"""Repeatable opt-in local model evaluation on synthetic fiction prompts.

Quality metrics are transparent diagnostics, not a universal prose score.
No user manuscript is read, no model downloaded, and only loopback Ollama is
permitted. The caller explicitly chooses which installed model to evaluate.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

SCENARIOS = (
    {
        "id": "belief-boundary",
        "name": "Character knowledge boundary",
        "prompt": (
            "Write an original third-person fantasy scene of 280-420 words. "
            "Ada believes the glass gate is harmless. The narrator knows the gate is "
            "dangerous, but do not reveal that truth to Ada. Bex must speak in short, "
            "pragmatic sentences, while Ada speaks in lyrical questions. End with "
            "the two characters agreeing to investigate tomorrow. Write narrative "
            "prose, not an outline."
        ),
        "required": ("Ada", "Bex", "gate"),
        "forbidden": ("Ada realized the gate was dangerous",),
        "min_words": 225,
        "max_words": 510,
    },
    {
        "id": "setup-payoff",
        "name": "Earned setup and payoff",
        "prompt": (
            "Write an original suspense scene of 280-420 words. Establish the "
            "sound of a silver bell early, then pay it off at the climax when "
            "Mara uses the bell to distract a pursuer. Preserve causality. "
            "Do not introduce a new person or a miracle to rescue Mara. "
            "Write immersive prose, not a beat sheet."
        ),
        "required": ("Mara", "bell"),
        "forbidden": ("she woke up from the dream",),
        "min_words": 225,
        "max_words": 510,
    },
    {
        "id": "scene-consequence",
        "name": "Scene aftermath and consequence",
        "prompt": (
            "Write an original fantasy scene of 280-420 words. Two friends, "
            "Niko and Jules, discover their maps disagree. Niko chooses to "
            "destroy one map so their pursuers cannot follow. This choice "
            "must worsen their immediate predicament and alter their trust. "
            "End with an unresolved but understandable decision. Prose only."
        ),
        "required": ("Niko", "Jules", "map"),
        "forbidden": ("all was forgiven",),
        "min_words": 225,
        "max_words": 510,
    },
)

TOKEN_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]", re.DOTALL)


def inspect_text(text: str, scenario: dict, elapsed_seconds: float | None = None) -> dict:
    """Return reproducible, evidence-based quality signals for a single response."""
    tokens = TOKEN_RE.findall(text)
    words = len(tokens)
    lowercase = text.casefold()
    missing = [word for word in scenario["required"] if word.casefold() not in lowercase]
    forbidden = [phrase for phrase in scenario["forbidden"] if phrase.casefold() in lowercase]
    normalized = [token.casefold() for token in tokens]
    grams = [tuple(normalized[i:i + 5]) for i in range(max(0, len(normalized) - 4))]
    frequency = Counter(grams)
    repeated = sorted(
        ((" ".join(gram), count) for gram, count in frequency.items() if count >= 3),
        key=lambda item: (-item[1], item[0]),
    )
    paragraphs = [part for part in re.split(r"\n\s*\n", text) if part.strip()]
    outline_like = bool(re.search(r"(?im)^\s*(?:\d+\.|[-*]\s+|scene\s+\d+:)", text))
    length_ok = scenario["min_words"] <= words <= scenario["max_words"]
    signals = {
        "nonempty": bool(text.strip()),
        "length": length_ok,
        "named_elements": not missing,
        "no_forbidden_reveal": not forbidden,
        "no_high_5gram_repetition": not repeated,
        "narrative_format": not outline_like and len(paragraphs) >= 2,
    }
    return {
        "scenario_id": scenario["id"], "name": scenario["name"],
        "word_count": words, "paragraph_count": len(paragraphs),
        "sentence_count": len(SENTENCE_RE.findall(text)),
        "missing_elements": missing, "forbidden_reveals": forbidden,
        "repeated_5grams": repeated[:12], "signals": signals,
        "passed": all(signals.values()),
        "elapsed_seconds": elapsed_seconds,
        "caveat": "Heuristics do not prove plot quality, emotion, consent, or factual continuity",
    }


async def run_benchmark(model: str, *, base_url: str = "http://127.0.0.1:11434",
                        timeout_seconds: float = 75,
                        on_progress: Callable[[int, int, dict], None] | None = None) -> dict:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Only the author's local Ollama loopback endpoint is allowed")
    if not model.strip() or len(model) > 200:
        raise ValueError("Choose one installed local model")
    if re.search(r"(?:^|[-:])(cloud|remote)(?:$|[-:])", model, re.IGNORECASE):
        raise ValueError("Cloud or remote Ollama aliases are never evaluated")
    results = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
        models = await client.get(base_url.rstrip("/") + "/api/tags")
        models.raise_for_status()
        available = {item.get("name") for item in models.json().get("models", [])}
        if model not in available:
            raise ValueError("This model is not installed in the local Ollama library")
        for scenario in SCENARIOS:
            import time
            start = time.monotonic()
            response = await client.post(base_url.rstrip("/") + "/api/generate", json={
                "model": model, "prompt": scenario["prompt"], "stream": False,
                "options": {"temperature": 0.65, "num_predict": 1450},
            })
            response.raise_for_status()
            data = response.json()
            report = inspect_text(str(data.get("response", "")), scenario,
                                  elapsed_seconds=round(time.monotonic() - start, 2))
            report["model_done"] = bool(data.get("done"))
            report["stop_reason"] = data.get("done_reason", "unknown")
            report["passed"] = report["passed"] and report["model_done"]
            results.append(report)
            if on_progress is not None:
                on_progress(len(results), len(SCENARIOS), report)
    return {
        "version": 1, "model": model, "kind": "synthetic-genre-evaluation",
        "generated_at": datetime.now(UTC).isoformat(), "scenarios": results,
        "passed": sum(item["passed"] for item in results),
        "total": len(results), "passing_fraction": round(
            statistics.mean(float(item["passed"]) for item in results), 3),
        "local_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate an installed local Ollama model")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = asyncio.run(run_benchmark(args.model, base_url=args.base_url))
    except (httpx.HTTPError, ValueError) as exc:
        parser.exit(2, f"Local benchmark unavailable: {exc}\n")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
