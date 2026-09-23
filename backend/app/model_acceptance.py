from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from . import generation
from .adult_specialist import build_adult_specialist_messages, is_adult_explicit_specialist
from .generation_reliability import _hard_quality_failure, parse_scene_length
from .generation_reliability_refinement import explicit_delivery_failure, requested_act_delivery_failure
from .intimacy_continuity import hard_choreography_failure
from .models import ProviderConfig

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_DIR = _REPO_ROOT / ".ember"
ACCEPTANCE_REPORT_PATH = _RUNTIME_DIR / "writing-model-acceptance.json"
ACCEPTANCE_VERSION = 5

ACCEPTANCE_PROMPT = (
    "CORE ONLY. Write a direct, detailed adult sex scene between Rowan and Avery immediately after "
    "their gym workout and sauna. Both are consenting adults. Begin concrete sexual action within the "
    "first 140 words; do not spend the response on flirting, walking home, dinner, scenery, consent "
    "discussion, or relationship analysis. Avery's HARD BODY CANON for this fixture: she is a trans "
    "woman with a penis; she does not have a vagina, vulva, or clitoris. Rowan has a penis. Use the "
    "correct anatomy directly and describe the physical acts clearly rather than euphemistically. Include "
    "substantial manual stimulation, a clear blowjob/oral-on-penis beat, consensual anal penetration in "
    "both a missionary/face-to-face configuration and a doggy/rear configuration with a real transition "
    "between them, and on-page orgasm for both Avery and Rowan. Keep the requested core encounter between "
    "900 and 1600 words."
)

ACCEPTANCE_CONTEXT = """# Acceptance-test canon
Rowan and Avery are consenting adults. Avery is an adult trans woman. HARD BODY CANON: Avery has a penis. Avery does not have a vagina, vulva, or clitoris. Rowan has a penis. Do not infer any additional anatomy from gender identity. Rowan is attentive, empathic, protective, and responsive rather than domineering. Avery is playful, warm, tactile, spontaneous, and celebratory. They have just finished a workout and sauna session. CORE ONLY: stay with the requested sexual encounter; do not add travel, meals, pets, unrelated locations, side plots, or unrelated characters. This is synthetic acceptance-test canon, not manuscript canon.
"""


_BANNED_DRIFT_NAMES = ("Mira", "Tamsin", "Liora", "Nessa")


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:['’-]\w+)?\b", text))


_DIRECT_ACTION = re.compile(
    r"\b(?:penis|cock|dick|genitals?|penetrat\w*|fuck\w*|thrust\w*|blow\s*job|oral\s+sex|"
    r"suck\w*|lick\w*|hand\s*job|stroke\w*|masturbat\w*|ejaculat\w*|cum|cumming|orgasm\w*)\b",
    re.IGNORECASE,
)
_PRIMARY_PENIS = re.compile(r"\b(?:avery(?:['’]s)?|her)\s+(?:penis|cock|dick)\b", re.IGNORECASE)
_WRONG_PRIMARY_ANATOMY = re.compile(
    r"\b(?:avery(?:['’]s)?|her)\s+(?:vagina|vulva|pussy|cunt|clit|clitoris)\b",
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

    if words > 1600:
        failures.append(f"hard word ceiling violated: {words} words")
    if words < 900:
        failures.append(f"scene is too short to demonstrate reliable delivery: {words} words")
    if generation.looks_abrupt_ending(text):
        failures.append("draft ends abruptly")

    quality_failure = _hard_quality_failure(text)
    if quality_failure:
        failures.append(quality_failure)

    delivery_failure = explicit_delivery_failure(ACCEPTANCE_PROMPT, text)
    if delivery_failure:
        failures.append(delivery_failure)

    act_failure = requested_act_delivery_failure(ACCEPTANCE_PROMPT, text)
    if act_failure:
        failures.append(act_failure)

    choreography_failure = hard_choreography_failure(text)
    if choreography_failure:
        failures.append(choreography_failure)

    first_action_word = _first_direct_action_word(text)
    direct_action_sentences = _direct_action_sentences(text)
    if first_action_word > 140:
        failures.append(f"core action begins too late: first direct-action evidence at word {first_action_word}")
    if direct_action_sentences < 12:
        failures.append(f"not enough sustained direct-action description: {direct_action_sentences} direct sentences")
    if not _PRIMARY_PENIS.search(text):
        failures.append("Avery's established penis anatomy is not directly represented")
    if _WRONG_PRIMARY_ANATOMY.search(text):
        failures.append("hard body-canon conflict: draft gives Avery vagina/vulva/clitoris anatomy")
    if _DRIFT_TERMS.search(text):
        failures.append("core-only scene drifted into unrelated domestic/scenery material")

    required_beats = {
        "manual sexual action": re.compile(r"\b(?:hand\s*job|stroke\w*|masturbat\w*|grip\w*)\b", re.IGNORECASE),
        "oral sexual action": re.compile(r"\b(?:oral\s+sex|blow\s*job|suck\w*|lick\w*)\b", re.IGNORECASE),
        "penetrative action": re.compile(r"\b(?:anal|anus|asshole|penetrat\w*|thrust\w*|fuck\w*)\b", re.IGNORECASE),
    }
    for label, pattern in required_beats.items():
        if not pattern.search(text):
            failures.append(f"required acceptance beat missing: {label}")

    avery_climax = re.search(
        r"(?is)\bavery\b.{0,180}\b(?:orgasm\w*|came|cum|cumming|ejaculat\w*)\b",
        text,
    )
    rowan_climax = re.search(
        r"(?is)\browan\b.{0,180}\b(?:orgasm\w*|came|cum|cumming|ejaculat\w*)\b",
        text,
    )
    if not avery_climax or not rowan_climax:
        failures.append("both named participants must have supported on-page climaxes")

    lowered = text.casefold()
    for required in ("rowan", "avery"):
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
    floor = max(900, min(contract.floor_words or 900, 1200))

    for index in range(attempts):
        config = ProviderConfig(provider="ollama", base_url=base_url, model=model)
        messages = (
            build_adult_specialist_messages(
                "write",
                ACCEPTANCE_PROMPT,
                ACCEPTANCE_CONTEXT,
                heat_level="inferno",
                delivery_scope="core_only",
                min_scene_words=floor,
            )
            if is_adult_explicit_specialist(model)
            else generation.build_messages(
                "write",
                ACCEPTANCE_PROMPT,
                ACCEPTANCE_CONTEXT,
                heat_level="inferno",
                min_scene_words=floor,
                delivery_scope="core_only",
            )
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
