from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter

import httpx

from . import generation_reliability as reliability
from . import generation_reliability_refinement as refinement
from . import streaming_generation
from .generation import MODEL_GATE, manuscript_role_failure
from .models import ProviderConfig
from .ollama_runtime import choose_installed_model, installed_ollama_models
from .performance_telemetry import record_model_call

DeltaCallback = Callable[[str], Awaitable[None]]
StatusCallback = Callable[[str], Awaitable[None]]

_LOCAL_STUDIO_MAX_PASSES = 2
_LOCAL_STUDIO_QUALITY_OUTPUT_TOKENS = 4096
_LOCAL_STUDIO_FAST_OUTPUT_TOKENS = 3072
_LOCAL_VERIFIER_CONTEXT_TOKENS = 8192
_LOCAL_VERIFIER_OUTPUT_TOKENS = 220
_VERIFIER_CONTEXT_CHARS = 12000
_VERIFIER_DRAFT_CHARS = 14000

_BASE_STREAMED_COMPLETE = streaming_generation.generate_complete_prose_streamed
_BASE_VERIFY = streaming_generation.verify_studio_scene_delivery
_INSTALLED = False


def _is_fast_model(model: str) -> bool:
    name = model.casefold()
    return "8b" in name or "8-b" in name or "8_b" in name


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


def _verified_from_payload(verdict: dict[str, object]) -> dict[str, object]:
    verified = all(
        (
            verdict.get("core_encounter_on_page") is True,
            verdict.get("requested_explicitness_delivered") is True,
            verdict.get("buildup_only") is False,
            verdict.get("fade_or_skip") is False,
            verdict.get("ending_complete") is True,
            verdict.get("canon_respected") is True,
            verdict.get("repetition_loop") is False,
        )
    )
    verdict["verified"] = verified
    return verdict


async def _verify_local_studio_scene_delivery(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    draft: str,
) -> dict[str, object]:
    """Run the semantic Studio judge with a small verifier-only Ollama context."""
    request_context = streaming_generation._verifier_source_context(messages)
    core_only = "Delivery scope: core-only." in request_context
    scope_instruction = (
        "CORE-ONLY VERIFICATION: judge only whether the requested central sexual action/encounter segment occurred on page "
        "and reached a natural stopping point. Do not require setup, consent discussion, relationship processing, emotional aftermath, "
        "or a complete surrounding scene. For core-only scope, ending_complete means the requested segment itself is complete."
        if core_only
        else "COMPLETE-SCENE VERIFICATION: require the requested encounter plus the immediate scene consequence/changed state."
    )
    verifier_messages = [
        {
            "role": "system",
            "content": (
                "You are EmberWriter's strict scene-delivery verifier. Do not rewrite, extend, sanitize, quote, or summarize "
                "the prose. Judge only whether the supplied draft actually fulfills the author's request. Return JSON only. "
                "For an adult intimacy request, distinguish an on-page sexual encounter from attraction, kissing, foreplay, "
                "buildup, euphemistic implication, fade-to-black, or skipping ahead. Mentions of requested acts inside assistant "
                "commentary, refusals, prompt echo, negative statements about what the draft lacks, or writing instructions DO NOT "
                "count as on-page scene delivery. Judge only actions that actually occur in manuscript narrative. Treat character "
                "identity, embodiment, body facts, participants, and relationship facts in the supplied request/context as hard canon. "
                "The author/story canon is authoritative for consent. If the author request or trusted project context establishes a "
                "consensual adult encounter, treat that consent state as settled and DO NOT require repeated verbal negotiation, permission "
                "checks, or safety discussion. Reject only when the draft itself directly contradicts that canon, such as ignoring an explicit "
                "stop/refusal or introducing coercion that the author did not request. "
                + scope_instruction
            ),
        },
        {
            "role": "user",
            "content": (
                "AUTHOR REQUEST AND RELEVANT CANON\n"
                f"{request_context}\n\n"
                "DRAFT TO VERIFY\n"
                f"{draft[-_VERIFIER_DRAFT_CHARS:]}\n\n"
                "Return exactly one JSON object with these keys:\n"
                '{"core_encounter_on_page":true|false,"requested_explicitness_delivered":true|false,'
                '"buildup_only":true|false,"fade_or_skip":true|false,"ending_complete":true|false,'
                '"canon_respected":true|false,"repetition_loop":true|false,"reason":"brief non-graphic explanation"}'
            ),
        },
    ]

    started = perf_counter()
    effective_model = config.model
    try:
        async with MODEL_GATE:
            installed = await installed_ollama_models(config.base_url)
            effective_model = choose_installed_model(config.model, installed)
            if not effective_model:
                return _failed_verdict("delivery verifier could not resolve the configured local model")
            if effective_model != config.model:
                config.model = effective_model

            body = {
                "model": effective_model,
                "messages": verifier_messages,
                "stream": False,
                "format": "json",
                "keep_alive": "30m",
                "options": {
                    "temperature": 0.0,
                    "top_p": 0.8,
                    "num_ctx": _LOCAL_VERIFIER_CONTEXT_TOKENS,
                    "num_predict": _LOCAL_VERIFIER_OUTPUT_TOKENS,
                },
            }
            timeout = httpx.Timeout(connect=15.0, read=600.0, write=60.0, pool=15.0)
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                response = await client.post(
                    f"{config.base_url.rstrip('/')}/api/chat",
                    json=body,
                )
                if response.status_code >= 400:
                    return _failed_verdict("delivery verifier could not complete")
                payload = response.json()
    except (RuntimeError, ValueError, httpx.HTTPError):
        return _failed_verdict("delivery verifier could not complete")

    record_model_call(
        stage="studio-verifier",
        model=effective_model,
        context_tokens=_LOCAL_VERIFIER_CONTEXT_TOKENS,
        performance_profile="fast" if _is_fast_model(effective_model) else "quality",
        payload=payload,
        total_ms=(perf_counter() - started) * 1000.0,
    )

    raw = str(payload.get("message", {}).get("content", ""))
    verdict = streaming_generation._parse_verifier_json(raw)
    if not verdict:
        return _failed_verdict("delivery verifier returned unreadable JSON")
    return _verified_from_payload(verdict)


async def verify_studio_scene_delivery_fast(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    draft: str,
) -> dict[str, object]:
    """Reject deterministic failures before paying for the semantic delivery judge."""
    role_failure = manuscript_role_failure(draft)
    if role_failure:
        return _failed_verdict(role_failure)

    quality_failure = reliability._hard_quality_failure(draft)
    if quality_failure:
        return _failed_verdict(
            f"deterministic prose gate rejected draft: {quality_failure[:220]}"
        )

    prompt = reliability._author_instruction(messages)
    delivery_failure = refinement.explicit_delivery_failure(prompt, draft)
    if delivery_failure:
        return _failed_verdict(delivery_failure, explicitness=True)

    if _is_local_studio(config, messages):
        return await _verify_local_studio_scene_delivery(config, messages, draft)
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
        profile = "Fast 8B" if _is_fast_model(config.model) else "Quality 12B"
        profile_cap = (
            _LOCAL_STUDIO_FAST_OUTPUT_TOKENS
            if _is_fast_model(config.model)
            else _LOCAL_STUDIO_QUALITY_OUTPUT_TOKENS
        )
        effective_output_tokens = min(max_output_tokens, profile_cap)
        if on_status is not None:
            await on_status(
                f"Local Studio · {profile} · primary draft + one repair pass maximum · compact semantic verifier"
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

    streaming_generation._VERIFIER_CONTEXT_CHARS = _VERIFIER_CONTEXT_CHARS
    streaming_generation._VERIFIER_DRAFT_CHARS = _VERIFIER_DRAFT_CHARS
    streaming_generation.verify_studio_scene_delivery = verify_studio_scene_delivery_fast
    streaming_generation.generate_complete_prose_streamed = generate_complete_prose_streamed_budgeted
    _INSTALLED = True
