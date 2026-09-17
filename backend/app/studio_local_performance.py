from __future__ import annotations

from collections.abc import Awaitable, Callable

from . import generation_reliability as reliability
from . import generation_reliability_refinement as refinement
from . import streaming_generation
from .models import ProviderConfig

DeltaCallback = Callable[[str], Awaitable[None]]
StatusCallback = Callable[[str], Awaitable[None]]

_LOCAL_STUDIO_MAX_PASSES = 2
_VERIFIER_CONTEXT_CHARS = 12000
_VERIFIER_DRAFT_CHARS = 14000

_BASE_STREAMED_COMPLETE = streaming_generation.generate_complete_prose_streamed
_BASE_VERIFY = streaming_generation.verify_studio_scene_delivery
_INSTALLED = False


def _is_local_studio(config: ProviderConfig, messages: list[dict[str, str]]) -> bool:
    return config.provider == "ollama" and streaming_generation._is_studio_scene(messages)


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


async def verify_studio_scene_delivery_fast(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    draft: str,
) -> dict[str, object]:
    """Reject deterministic failures before spending another local-model call on verification.

    The previous order always invoked the 12B verifier first and only then applied deterministic
    explicitness/quality checks. A clearly euphemistic or structurally broken draft therefore paid
    for an expensive judge call even though EmberWriter already knew it could not be accepted.
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
    """Keep local Studio to one primary pass plus at most one targeted repair pass."""
    effective_passes = max_passes
    if _is_local_studio(config, messages):
        effective_passes = min(max_passes, _LOCAL_STUDIO_MAX_PASSES)
        if on_status is not None:
            await on_status("Local Studio · primary draft + one repair pass maximum")

    return await _BASE_STREAMED_COMPLETE(
        config,
        messages,
        min_words=min_words,
        on_delta=on_delta,
        on_status=on_status,
        max_passes=effective_passes,
        max_output_tokens=max_output_tokens,
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
    # evaluation time and KV pressure on local models.
    streaming_generation._VERIFIER_CONTEXT_CHARS = _VERIFIER_CONTEXT_CHARS
    streaming_generation._VERIFIER_DRAFT_CHARS = _VERIFIER_DRAFT_CHARS
    streaming_generation.verify_studio_scene_delivery = verify_studio_scene_delivery_fast
    streaming_generation.generate_complete_prose_streamed = generate_complete_prose_streamed_budgeted
    _INSTALLED = True
