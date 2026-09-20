from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from . import generation
from .generation_reliability import _hard_quality_failure, parse_scene_length
from .generation_reliability_refinement import explicit_delivery_failure
from .models import ProviderConfig

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_DIR = _REPO_ROOT / ".ember"
ACCEPTANCE_REPORT_PATH = _RUNTIME_DIR / "writing-model-acceptance.json"
ACCEPTANCE_VERSION = 3

ACCEPTANCE_PROMPT = (
    "CORE ONLY. Write a direct, detailed adult sex scene between Kaelen and Muna immediately after "
    "their gym workout and sauna. Both are consenting adults. Begin concrete sexual action within the "
    "first 180 words; do not spend the response on flirting, walking home, dinner, scenery, consent "
    "discussion, or relationship analysis. Muna's HARD BODY CANON for this fixture: she is a trans "
    "woman with a penis; she does not have a vagina, vulva, or clitoris. Kaelen has a penis. Use the "
    "correct anatomy directly and describe the physical acts clearly rather than euphemistically. "
    "Both participants must climax on page. Keep the requested core encounter between 500 and 1000 words."
)

ACCEPTANCE_CONTEXT = """# Acceptance-test canon
Kaelen and Muna are consenting adults. Muna is an adult trans woman. HARD BODY CANON: Muna has a penis. Muna does not have a vagina, vulva, or clitoris. Kaelen has a penis. Do not infer any additional anatomy from gender identity. Kaelen is the Nexus: attentive, empathic, protective, and responsive rather than domineering. Muna's Joy/Ecstasy resonance is playful, warm, musical, tactile, spontaneous, and celebratory, with amber/rose/gold imagery. They have just finished a workout and sauna session. CORE ONLY: stay with the requested sexual encounter; do not add travel, meals, pets, unrelated locations, side plots, or unrelated characters. This is synthetic acceptance-test canon, not manuscript canon.
"""


_BANNED_DRIFT_NAMES = ("Sera", "Jax", "Elara", "Lyra")


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:['’-]\w+)?\b", text))


_DIRECT_ACTION = re.compile(
    r"\b(?:penis|cock|dick|genitals?|penetrat\w*|fuck\w*|thrust\w*|blow\s*job|oral\s+sex|"
    r"suck\w*|lick\w*|hand\s*job|stroke\w*|masturbat\w*|ejaculat\w*|cum|cumming|orgasm\w*)\b",
    re.IGNORECASE,
)
_MUNA_PENIS = re.compile(r"\b(?:muna(?:['’]s)?|her)\s+(?:penis|cock|dick)\b", re.IGNORECASE)
_WRONG_MUNA_ANATOMY = re.compile(
    r"\b(?:muna(?:['’]s)?|her)\s+(?:vagina|vulva|pussy|cunt|clit|clitoris)\b",
    re.IGNORECASE,
)
_DRIFT_TERMS = re.compile(
    r"\b(?:pet\s+bunny|coffee\s+brewing|dinner|red\s+wine|riverbank|living\s+area|high\s+school)\b",
    re.IGNORECASE,
)


def _first_direct_action_word(text: str) -> int:
    match = _DIRECT_ACTION.search(text)
    if not match:
        return 10_000
    return _word_count(text[: match.start()])


def _direct_action_sentences(text: str) -> int:
    sentences = [part for part in re.split(r"(?<=[.!?…])\s+|\n+", text) if part.strip()]
    return sum(bool(_DIRECT_ACTION.search(sentence)) for sentence in sentences)


def evaluate_acceptance_output(text: str) -> dict[str, object]:
    words = _word_count(text)
    failures: list[str] = []

    if words > 1000:
        failures.append(f"hard word ceiling violated: {words} words")
    if words < 500:
        failures.append(f"scene is too short to demonstrate reliable delivery: {words} words")
    if generation.looks_abrupt_ending(text):
        failures.append("draft ends abruptly")

    quality_failure = _hard_quality_failure(text)
    if quality_failure:
        failures.append(quality_failure)

    delivery_failure = explicit_delivery_failure(ACCEPTANCE_PROMPT, text)
    if delivery_failure:
        failures.append(delivery_failure)

    first_action_word = _first_direct_action_word(text)
    direct_action_sentences = _direct_action_sentences(text)
    if first_action_word > 180:
        failures.append(f"core action begins too late: first direct-action evidence at word {first_action_word}")
    if direct_action_sentences < 5:
        failures.append(f"not enough sustained direct-action description: {direct_action_sentences} direct sentences")
    if not _MUNA_PENIS.search(text):
        failures.append("Muna's established penis anatomy is not directly represented")
    if _WRONG_MUNA_ANATOMY.search(text):
        failures.append("hard body-canon conflict: draft gives Muna vagina/vulva/clitoris anatomy")
    if _DRIFT_TERMS.search(text):
        failures.append("core-only scene drifted into unrelated domestic/scenery material")

    lowered = text.casefold()
    for required in ("kaelen", "muna"):
        if required not in lowered:
            failures.append(f"required participant missing from prose: {required}")

    drift = [name for name in _BANNED_DRIFT_NAMES if re.search(rf"\b{re.escape(name)}\b", text)]
    if drift:
        failures.append("unrelated character drift: " + ", ".join(drift))

    return {
        "passed": not failures,
        "word_count": words,
        "first_direct_action_word": first_action_word,
        "direct_action_sentences": direct_action_sentences,
        "failures": failures,
    }


async def run_model_acceptance(
    model: str,
    *,
    base_url: str = "http://localhost:11434",
    attempts: int = 3,
) -> dict[str, object]:
    attempts = max(1, min(attempts, 5))
    results: list[dict[str, object]] = []
    effective_models: list[str] = []

    try:
        installed = await generation.installed_ollama_models(base_url)
    except (RuntimeError, ValueError, OSError) as exc:
        return {
            "acceptance_version": ACCEPTANCE_VERSION,
            "updated_at": datetime.now(UTC).isoformat(),
            "requested_model": model,
            "effective_models": [],
            "attempts": attempts,
            "passes": 0,
            "required_passes": attempts if attempts <= 3 else attempts - 1,
            "passed": False,
            "results": [{
                "attempt": 0,
                "model": model,
                "passed": False,
                "word_count": 0,
                "failures": [f"could not inspect installed models: {type(exc).__name__}: {exc}"],
            }],
        }
    installed_by_name = {item.casefold(): item for item in installed}
    exact = installed_by_name.get(model.casefold())
    if not exact:
        return {
            "acceptance_version": ACCEPTANCE_VERSION,
            "updated_at": datetime.now(UTC).isoformat(),
            "requested_model": model,
            "effective_models": [],
            "attempts": attempts,
            "passes": 0,
            "required_passes": attempts if attempts <= 3 else attempts - 1,
            "passed": False,
            "results": [{
                "attempt": 0,
                "model": model,
                "passed": False,
                "word_count": 0,
                "failures": ["candidate model is not installed; acceptance will not substitute another model"],
            }],
        }
    model = exact

    contract = parse_scene_length(ACCEPTANCE_PROMPT, "inferno")
    floor = max(500, min(contract.floor_words or 500, 700))

    for index in range(attempts):
        config = ProviderConfig(provider="ollama", base_url=base_url, model=model)
        messages = generation.build_messages(
            "write",
            ACCEPTANCE_PROMPT,
            ACCEPTANCE_CONTEXT,
            heat_level="inferno",
            min_scene_words=floor,
            delivery_scope="core_only",
        )
        try:
            text = await generation.generate_complete_prose(
                config,
                messages,
                min_words=floor,
                max_passes=3,
                max_output_tokens=2600,
            )
            assessment = evaluate_acceptance_output(text)
            assessment["attempt"] = index + 1
            assessment["model"] = config.model
            results.append(assessment)
            effective_models.append(config.model)
        except (RuntimeError, ValueError, OSError) as exc:
            results.append(
                {
                    "attempt": index + 1,
                    "model": config.model,
                    "passed": False,
                    "word_count": 0,
                    "failures": [f"generation error: {type(exc).__name__}: {exc}"],
                }
            )
            effective_models.append(config.model)

    passes = sum(result.get("passed") is True for result in results)
    required_passes = attempts if attempts <= 3 else attempts - 1
    report = {
        "acceptance_version": ACCEPTANCE_VERSION,
        "updated_at": datetime.now(UTC).isoformat(),
        "requested_model": model,
        "effective_models": sorted(set(effective_models)),
        "attempts": attempts,
        "passes": passes,
        "required_passes": required_passes,
        "passed": passes >= required_passes,
        "results": results,
    }
    return report


def write_acceptance_report(report: dict[str, object]) -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    ACCEPTANCE_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EmberWriter's real local-model writing acceptance test")
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()

    report = asyncio.run(
        run_model_acceptance(
            args.model,
            base_url=args.base_url,
            attempts=args.attempts,
        )
    )
    write_acceptance_report(report)
    print(json.dumps(report, indent=2))
    return 0 if report.get("passed") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
