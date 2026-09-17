from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from . import generation_reliability as reliability
from . import generation_reliability_refinement as refinement
from . import streaming_generation
from .models import ProviderConfig

DeltaCallback = Callable[[str], Awaitable[None]]
StatusCallback = Callable[[str], Awaitable[None]]

_LOCAL_STUDIO_MAX_PASSES = 2
_LOCAL_STUDIO_MAX_OUTPUT_TOKENS = 4096
_LOCAL_STUDIO_LLM_VERIFIER_ENV = "EMBER_LOCAL_STUDIO_LLM_VERIFIER"
_VERIFIER_CONTEXT_CHARS = 12000
_VERIFIER_DRAFT_CHARS = 14000

_BASE_STREAMED_COMPLETE = streaming_generation.generate_complete_prose_streamed
_BASE_VERIFY = streaming_generation.verify_studio_scene_delivery
_INSTALLED = False


def _is_local_studio(config: ProviderConfig, messages: list[dict[str, str]]) -> bool:
    return config.provider == "ollama" and streaming_generation._is_studio_scene(messages)


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _failed_verdict(reason: str, *, explicitness: bool = False) -> dict[str, object]:
    verdict: dict[str, object] = {
        "verified": False,
        "canon_respected": True,
        "repetition_loop": False,
        "reason": reason,
    }
    if explicitness:
        verdict["requested_explicitness_delivered"] = False
    return verdict


def _deterministic_success_verdict() -> dict[str, object]:
    return {
        "verified": True,
        "core_encounter_on_page": True,
        "requested_explicitness_delivered": True,
        "buildup_only": False,
        "fade_or_skip": False,
        "ending_complete": True,
        "canon_respected": True,
        "repetition_loop": False,
        "reason": "local Studio deterministic delivery gates accepted the completed scene",
    }


async def verify_studio_scene_delivery_fast(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    draft: str,
) -> dict[str, object]:
    """Use cheap deterministic delivery gates before an optional local-model judge.

    The streaming pipeline only invokes this verifier after a candidate has already emitted the
    explicit scene-complete marker, met the requested word floor, reached a natural sentence ending,
    and produced new candidate prose. Re-running the same 12B model as an independent judge can add
    another full prompt-evaluation/inference cycle to an otherwise finished local scene.

    For local Studio, deterministic prose/explicitness gates are therefore the default final check.
    Authors who prefer the slower independent LLM judge can opt back in with
    EMBER_LOCAL_STUDIO_LLM_VERIFIER=1. Non-local providers keep the independent verifier.
    """
    quality_failure = reliability._hard_quality_failure(draft)
    if quality_failure:
        return _failed_verdict(
            f"deterministic prose gate rejected draft: {quality_failure[:220]}"
        )

    prompt = reliability._author_instruction(messages)
    delivery_failure = refinement.explicit_delivery_failure(prompt, draft)
    if delivery_failure:
        return _failed_verdict(delivery_failure, explicitness=True)

    if _is_local_studio(config, messages) and not _env_enabled(_LOCAL_STUDIO_LLM_VERIFIER_ENV):
        return _deterministic_success_verdict()

    return await _BASE_VERIFY(config, messages, draft)


async def generate_complete_prose_streamed_budgeted(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    min_words: int,
    on_delta: DeltaCallback,
    on_status: StatusCallback | None = None,
    max_passes: int = 6,
    max_output_tokens: int = 6144,
) -> str:
    """Bound local Studio inference while preserving one targeted repair pass."""
    effective_passes = max_passes
    effective_output_tokens = max_output_tokens
    if _is_local_studio(config, messages):
        effective_passes = min(max_passes, _LOCAL_STUDIO_MAX_PASSES)
        effective_output_tokens = min(max_output_tokens, _LOCAL_STUDIO_MAX_OUTPUT_TOKENS)
        if on_status is not None:
            verifier_mode = (
                "strict LLM verifier"
                if _env_enabled(_LOCAL_STUDIO_LLM_VERIFIER_ENV)
                else "fast deterministic verifier"
            )
            await on_status(
                "Local Studio · primary draft + one repair pass maximum · "
                f"{verifier_mode}"
            )

    return await _BASE_STREAMED_COMPLETE(
        config,
        messages,
        min_words=min_words,
        on_delta=on_delta,
        on_status=on_status,
        max_passes=effective_passes,
        max_output_tokens=effective_output_tokens,
    )


def install_studio_local_performance() -> None:
    """Install the bounded local Studio pipeline exactly once."""
    global _BASE_STREAMED_COMPLETE, _BASE_VERIFY, _INSTALLED
    if _INSTALLED:
        return

    _BASE_STREAMED_COMPLETE = streaming_generation.generate_complete_prose_streamed
    _BASE_VERIFY = streaming_generation.verify_studio_scene_delivery

    # The verifier only needs enough request/canon context to judge the delivered scene, not the
    # same broad context window used to write it. Smaller verifier prompts materially reduce prompt
    # evaluation time and KV pressure on local models when strict verification is explicitly enabled.
    streaming_generation._VERIFIER_CONTEXT_CHARS = _VERIFIER_CONTEXT_CHARS
    streaming_generation._VERIFIER_DRAFT_CHARS = _VERIFIER_DRAFT_CHARS
    streaming_generation.verify_studio_scene_delivery = verify_studio_scene_delivery_fast
    streaming_generation.generate_complete_prose_streamed = generate_complete_prose_streamed_budgeted
    _INSTALLED = True
