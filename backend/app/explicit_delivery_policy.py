from __future__ import annotations

import json
import re

from . import craft
from . import generation_reliability as reliability
from . import generation_reliability_refinement as refinement
from . import model_provisioning
from . import ollama_runtime
from . import streaming_generation as streaming

HERETIC_ROCINANTE_MODEL = (
    "hf.co/mradermacher/Rocinante-X-12B-v1-Heretic-Uncensored-GGUF:Q4_K_M"
)
EXPLICIT_ACCEPTANCE_VERSION = 2

_DECENSOR_MARKERS = ("heretic", "uncensored", "abliter", "decensor")
_CREATIVE_MARKERS = (
    "cydonia",
    "rocinante",
    "magidonia",
    "magnum",
    "mag-mell",
    "mag_mell",
    "stheno",
    "pygmalion",
    "lunaris",
    "nemomix",
)

_ANATOMY_PATTERNS = (
    r"\b(?:penis|cock|dick)\b",
    r"\b(?:vagina|pussy|cunt|clit|clitoris)\b",
    r"\b(?:anus|asshole|genitals?|genitalia)\b",
)
_ACTION_PATTERNS = (
    r"\bpenetrat(?:e|ed|es|ing|ion)\b",
    r"\b(?:fuck|fucked|fucking|thrust|thrusted|thrusting|thrusts)\b",
    r"\b(?:blow\s*job|hand\s*job|oral\s+sex)\b",
    r"\b(?:suck|sucked|sucking|lick|licked|licking)\b",
    r"\b(?:masturbat\w*|stroke|stroked|stroking)\b",
)
_RELEASE_PATTERNS = (
    r"\b(?:semen|ejaculat\w*|cum|cumming)\b",
    r"\b(?:orgasm|orgasmed|climax|climaxed|came)\b",
)

_base_explicit_delivery_failure = refinement.explicit_delivery_failure
_base_quality_pass = craft.quality_pass
_base_route_adult_model = reliability._route_adult_model
_base_run_acceptance = model_provisioning._run_acceptance
_base_generate_complete_prose_streamed = None


def is_decensored_creative_model(model: str) -> bool:
    name = model.casefold()
    return any(marker in name for marker in _CREATIVE_MARKERS) and any(
        marker in name for marker in _DECENSOR_MARKERS
    )


def explicit_creative_model_score(model: str) -> int:
    name = model.casefold()
    decensored = any(marker in name for marker in _DECENSOR_MARKERS)
    if "cydonia" in name and decensored:
        return 310
    if "rocinante-x" in name and decensored:
        return 300
    if "rocinante" in name and decensored:
        return 290
    if any(token in name for token in ("magidonia", "magnum", "mag-mell", "mag_mell")) and decensored:
        return 275
    if any(token in name for token in ("stheno", "pygmalion", "lunaris", "nemomix")) and decensored:
        return 260
    return 0


def adult_route_score(model: str) -> int:
    explicit_score = explicit_creative_model_score(model)
    if explicit_score:
        return explicit_score
    name = model.casefold()
    if "qwen2.5-14b" in name and "heretic" in name:
        return 150
    if "qwen3-8b" in name and "heretic" in name:
        return 140
    if any(marker in name for marker in _DECENSOR_MARKERS):
        return 120
    # A normal creative/RP model is not enough for a request that explicitly requires direct
    # sexual prose. Prose quality and willingness to deliver explicit content are separate skills.
    return 0


def has_explicit_creative_model(models: list[str]) -> bool:
    return any(is_decensored_creative_model(model) for model in models)


def best_explicit_creative_model(models: list[str]) -> str | None:
    ranked = sorted(models, key=explicit_creative_model_score, reverse=True)
    if not ranked or explicit_creative_model_score(ranked[0]) <= 0:
        return None
    return ranked[0]


def _has_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def strict_explicit_delivery_failure(prompt: str, draft: str) -> str:
    base_failure = _base_explicit_delivery_failure(prompt, draft)
    if base_failure:
        return base_failure
    if not refinement.requires_direct_explicitness(prompt):
        return ""

    has_anatomy = _has_pattern(draft, _ANATOMY_PATTERNS)
    has_action = _has_pattern(draft, _ACTION_PATTERNS)
    has_release = _has_pattern(draft, _RELEASE_PATTERNS)

    if not has_anatomy:
        return (
            "author requested direct explicit scene delivery, but the draft avoids direct "
            "anatomical language and reads as euphemistic/PG-13"
        )
    if not has_action:
        return (
            "author requested direct explicit scene delivery, but the draft avoids direct "
            "sexual-action language and substitutes implication or summary"
        )
    if not has_release:
        return "author requested explicit completion, but the draft lacks direct climax/release evidence"

    # Do not let a glossary-like mention of anatomy in one place and a vague action elsewhere
    # satisfy the gate. At least one paragraph must contain both anatomy and a direct act.
    paragraphs = [part for part in re.split(r"\n\s*\n", draft) if part.strip()]
    if not any(
        _has_pattern(paragraph, _ANATOMY_PATTERNS) and _has_pattern(paragraph, _ACTION_PATTERNS)
        for paragraph in paragraphs
    ):
        return (
            "author requested direct explicit scene delivery, but anatomy and sexual action never "
            "appear together in an on-page beat"
        )
    return ""


async def strict_quality_pass(
    provider,
    draft: str,
    author_prompt: str,
    craft_context: str,
) -> str:
    revised = await _base_quality_pass(
        provider,
        draft=draft,
        author_prompt=author_prompt,
        craft_context=craft_context,
    )
    # The model-based Craft verifier is useful for continuity, but it cannot be the sole judge
    # of whether an explicit scene was quietly sanitized during editing.
    if strict_explicit_delivery_failure(author_prompt, revised):
        return draft
    return revised


async def strict_route_adult_model(config, messages) -> None:
    prompt = reliability._author_instruction(messages)
    direct_explicit_request = refinement.requires_direct_explicitness(prompt)
    if (
        config.provider != "ollama"
        or not reliability._is_intimacy_request(messages)
        or not direct_explicit_request
    ):
        await _base_route_adult_model(config, messages)
        return

    installed = await ollama_runtime.installed_ollama_models(config.base_url)
    candidates = [model for model in installed if is_decensored_creative_model(model)]
    if not candidates:
        raise RuntimeError(
            "No decensored creative writing model is ready for this explicit scene. "
            "EmberWriter is provisioning its explicit-writing model; refusing to fall back "
            "to a tame model and return another PG-13 draft."
        )
    config.model = max(candidates, key=explicit_creative_model_score)


async def strict_generate_complete_prose_streamed(
    config,
    messages,
    *,
    min_words: int,
    on_delta,
    on_status=None,
    max_passes: int = 6,
    max_output_tokens: int = 6144,
) -> str:
    prompt = reliability._author_instruction(messages)
    base = _base_generate_complete_prose_streamed
    if base is None:
        raise RuntimeError("Explicit delivery policy was not fully initialized")

    if not refinement.requires_direct_explicitness(prompt):
        return await base(
            config,
            messages,
            min_words=min_words,
            on_delta=on_delta,
            on_status=on_status,
            max_passes=max_passes,
            max_output_tokens=max_output_tokens,
        )

    # Direct explicit requests fail closed. Buffer the prose until the independent delivery
    # verifier accepts it, so a rejected PG-13 attempt can never leak through routes_generation
    # as a saved "partial" Working Draft merely because some deltas were already visible.
    buffered: list[str] = []

    async def buffer_delta(text: str) -> None:
        if text:
            buffered.append(text)

    text = await base(
        config,
        messages,
        min_words=min_words,
        on_delta=buffer_delta,
        on_status=on_status,
        max_passes=max_passes,
        max_output_tokens=max_output_tokens,
    )
    failure = strict_explicit_delivery_failure(prompt, text)
    if failure:
        raise streaming.SceneDeliveryIncomplete("", failure)

    # Only verified prose becomes author-visible. The normal final event still carries the same
    # text, while this delta lets the streaming popup populate once verification has succeeded.
    await on_delta(text)
    return text


def _cached_acceptance_passed(model: str) -> bool:
    try:
        payload = json.loads(model_provisioning._ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    if payload.get("acceptance_version") != EXPLICIT_ACCEPTANCE_VERSION:
        return False
    if payload.get("passed") is not True:
        return False
    requested = str(payload.get("requested_model", "")).casefold()
    effective = [str(value).casefold() for value in payload.get("effective_models", []) if value]
    target = model.casefold()
    return requested == target or target in effective


def _run_acceptance_and_stamp(model: str, installed: list[str], auto_installed: bool) -> None:
    _base_run_acceptance(model, installed, auto_installed)
    try:
        payload = json.loads(model_provisioning._ACCEPTANCE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict) or payload.get("passed") is not True:
        return
    payload["acceptance_version"] = EXPLICIT_ACCEPTANCE_VERSION
    try:
        model_provisioning._ACCEPTANCE_PATH.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )
    except OSError:
        return


def install_explicit_delivery_policy() -> None:
    global _base_generate_complete_prose_streamed

    # Capture the already-installed reliability wrapper here, not at module import time. That
    # preserves hard word ceilings, repetition recovery, and Studio delivery verification underneath
    # the new fail-closed visibility layer.
    _base_generate_complete_prose_streamed = streaming.generate_complete_prose_streamed

    # Provision an actually decensored creative/RP model. Hugging Face publishes this GGUF with
    # an Ollama invocation, so it remains a one-command local model while avoiding the high
    # refusal behavior of the ordinary Rocinante family for direct explicit requests.
    model_provisioning.BASELINE_CREATIVE_MODEL = HERETIC_ROCINANTE_MODEL
    model_provisioning._ACCEPTANCE_VERSION = EXPLICIT_ACCEPTANCE_VERSION
    model_provisioning.has_creative_model = has_explicit_creative_model
    model_provisioning._creative_model_score = explicit_creative_model_score
    model_provisioning._best_creative_model = best_explicit_creative_model
    model_provisioning._cached_acceptance_passed = _cached_acceptance_passed
    model_provisioning._run_acceptance = _run_acceptance_and_stamp

    reliability.adult_model_score = adult_route_score
    reliability._route_adult_model = strict_route_adult_model
    refinement.refined_adult_model_score = adult_route_score
    refinement.explicit_delivery_failure = strict_explicit_delivery_failure
    # refined_verify_studio_scene_delivery resolves explicit_delivery_failure from its module
    # globals at call time, so replacing the symbol above hardens the existing verifier too.

    craft.quality_pass = strict_quality_pass
    streaming.generate_complete_prose_streamed = strict_generate_complete_prose_streamed

    ollama_runtime._RECOMMENDED_MODELS = (
        "Fermi/Cydonia-24B-v4.3-heretic-vision:Q4_K_M",
        HERETIC_ROCINANTE_MODEL,
        "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m",
        "R4C3R/qwen3-8b-heretic:q4_k_m",
    )
