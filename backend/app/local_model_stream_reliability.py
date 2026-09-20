from __future__ import annotations

import asyncio
import json
import os
from time import perf_counter

import httpx

from . import streaming_generation
from .generation import MODEL_GATE, OLLAMA_CONTEXT_TOKENS
from .models import ProviderConfig
from .ollama_runtime import choose_installed_model, installed_ollama_models
from .performance_telemetry import record_model_call
from .writing_model_catalog import (
    FAST_ADULT_8B,
    HIGH_HEAT_CYDONIA_24B,
    HERETIC_ROCINANTE_12B,
    MAGNUM_V4_12B,
    PYGMALION_3_12B,
    STANDARD_ROCINANTE_12B,
    preferred_adult_model,
)

_FIRST_TOKEN_TIMEOUT_SECONDS = 15 * 60
_INTER_TOKEN_TIMEOUT_SECONDS = 5 * 60
_LARGE_MODEL_CONTEXT_TOKENS = 16384
_LARGE_MODEL_HINTS = ("cydonia", "24b", "24-b", "24_b")
_PYGMALION_ADULT = PYGMALION_3_12B
_MAGNUM_ADULT = MAGNUM_V4_12B
_HERETIC_ROCINANTE = HERETIC_ROCINANTE_12B
_STANDARD_ROCINANTE = STANDARD_ROCINANTE_12B
_HIGH_HEAT_CYDONIA = HIGH_HEAT_CYDONIA_24B
_FAST_ADULT_MODEL = FAST_ADULT_8B

_ORIGINAL_GENERATE_STREAMED = streaming_generation.generate_streamed
_INSTALLED = False


def _is_fast_model(model: str) -> bool:
    name = model.casefold()
    return "8b" in name or "8-b" in name or "8_b" in name


def _estimated_message_tokens(messages: list[dict[str, str]]) -> int:
    """Cheap conservative tokenizer estimate suitable for context-window budgeting."""
    chars = sum(len(str(message.get("content", ""))) for message in messages)
    return max(1, chars // 4 + len(messages) * 12)


def ollama_context_tokens_for(
    model: str,
    messages: list[dict[str, str]] | None = None,
    max_output_tokens: int | None = None,
) -> int:
    """Choose the smallest practical Ollama context for the actual request.

    A large configured context reserves more KV memory even when the prompt is smaller. Studio uses
    bounded context candidates so an 8B model can fit into VRAM more easily and the 12B quality model
    does not pay for a 24K window when 10K-16K is enough.
    """
    lowered = model.casefold()
    context_tokens = OLLAMA_CONTEXT_TOKENS
    if any(hint in lowered for hint in _LARGE_MODEL_HINTS):
        context_tokens = min(context_tokens, _LARGE_MODEL_CONTEXT_TOKENS)

    if not messages or not streaming_generation._is_studio_scene(messages):
        return context_tokens

    fast = _is_fast_model(model)
    output_budget = max_output_tokens or (3072 if fast else 4096)
    output_budget = min(max(output_budget, 512), 4096)
    required = _estimated_message_tokens(messages) + output_budget + 768
    candidates = (8192, 10240, 12288) if fast else (10240, 12288, 16384)
    selected = candidates[-1]
    for candidate in candidates:
        if required <= candidate:
            selected = candidate
            break
    return min(context_tokens, selected)


async def _next_line(iterator, timeout_seconds: float) -> str | None:
    try:
        return await asyncio.wait_for(iterator.__anext__(), timeout=timeout_seconds)
    except StopAsyncIteration:
        return None


async def route_adult_model_stable(
    config: ProviderConfig,
    messages: list[dict[str, str]],
) -> None:
    """Repair stale model choices without upgrading a valid configured creative model."""
    from . import generation_reliability as reliability

    if config.provider != "ollama" or not reliability._is_intimacy_request(messages):
        return
    if config.lock_model:
        return

    installed = await installed_ollama_models(config.base_url)
    if not installed:
        return

    measured_or_preferred = preferred_adult_model(installed)
    current = next(
        (item for item in installed if item.casefold() == config.model.casefold()),
        None,
    )

    # Auto mode follows the capability-slot winner even when its static family score is lower
    # than another installed model. Static scores bootstrap routing before a bakeoff exists;
    # measured acceptance results are authoritative afterward. Manual author choices return
    # above via lock_model=True.
    if measured_or_preferred:
        config.model = measured_or_preferred
        return

    if current and reliability.adult_model_score(current) > 0:
        config.model = current


async def generate_streamed_reliable(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    on_delta: streaming_generation.DeltaCallback,
    temperature: float = 0.9,
    top_p: float = 0.95,
    json_mode: bool = False,
    max_output_tokens: int | None = None,
) -> str:
    """Ollama stream path with adaptive context, telemetry, and state-aware watchdogs."""
    if config.provider != "ollama":
        return await _ORIGINAL_GENERATE_STREAMED(
            config,
            messages,
            on_delta=on_delta,
            temperature=temperature,
            top_p=top_p,
            json_mode=json_mode,
            max_output_tokens=max_output_tokens,
        )

    if not config.model.strip():
        raise ValueError("Choose a model before generating")

    call_started = perf_counter()
    async with MODEL_GATE:
        installed = await installed_ollama_models(config.base_url)
        effective_model = choose_installed_model(config.model, installed)
        if not effective_model:
            raise RuntimeError(
                "Ollama is running, but no local writing models are installed. "
                "EmberWriter did not delete or replace a model; the Ollama library is empty."
            )
        if effective_model != config.model:
            config.model = effective_model

        context_tokens = ollama_context_tokens_for(
            effective_model,
            messages,
            max_output_tokens=max_output_tokens,
        )
        options: dict[str, float | int] = {
            "temperature": temperature,
            "top_p": top_p,
            "num_ctx": context_tokens,
            "repeat_penalty": streaming_generation._OLLAMA_REPEAT_PENALTY,
            "repeat_last_n": streaming_generation._OLLAMA_REPEAT_LAST_N,
        }
        if max_output_tokens is not None:
            options["num_predict"] = max_output_tokens

        body: dict = {
            "model": effective_model,
            "messages": messages,
            "stream": True,
            "keep_alive": "30m",
            "options": options,
        }
        if json_mode:
            body["format"] = "json"

        pieces: list[str] = []
        final_metrics: dict[str, object] = {}
        first_token_ms: float | None = None
        timeout = httpx.Timeout(connect=15.0, read=None, write=120.0, pool=15.0)
        try:
            async with (
                httpx.AsyncClient(timeout=timeout, trust_env=False) as client,
                client.stream(
                    "POST",
                    f"{config.base_url.rstrip('/')}/api/chat",
                    json=body,
                ) as response,
            ):
                if response.status_code >= 400:
                    payload = await response.aread()
                    detail = payload.decode("utf-8", errors="replace")[:500].strip()
                    raise RuntimeError(
                        f"Ollama could not generate with {effective_model}: "
                        f"{detail or f'HTTP {response.status_code}'}"
                    )

                line_iterator = response.aiter_lines().__aiter__()
                saw_text = False
                while True:
                    watchdog = (
                        _INTER_TOKEN_TIMEOUT_SECONDS if saw_text else _FIRST_TOKEN_TIMEOUT_SECONDS
                    )
                    try:
                        line = await _next_line(line_iterator, watchdog)
                    except TimeoutError as exc:
                        if saw_text:
                            raise RuntimeError(
                                "The local writing model stopped sending output for 5 minutes after generation had started, "
                                "so EmberWriter ended the stalled request."
                            ) from exc
                        model_note = (
                            " The selected 24B model may be too large for the available GPU/CPU path; "
                            "use the Quality 12B or Fast 8B Studio profile instead."
                            if any(hint in effective_model.casefold() for hint in _LARGE_MODEL_HINTS)
                            else ""
                        )
                        raise RuntimeError(
                            "The local writing model did not produce its first token within 15 minutes. "
                            "Ollama may still be loading the model or processing a very large prompt."
                            + model_note
                        ) from exc

                    if line is None:
                        break
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise RuntimeError("Ollama returned an invalid streaming response") from exc
                    if payload.get("error"):
                        raise RuntimeError(f"Ollama generation failed: {payload['error']}")
                    if payload.get("done"):
                        final_metrics = payload
                    piece = str(payload.get("message", {}).get("content", ""))
                    if piece:
                        if not saw_text:
                            first_token_ms = (perf_counter() - call_started) * 1000.0
                        saw_text = True
                        pieces.append(piece)
                        await on_delta(piece)
        except httpx.ConnectError as exc:
            raise RuntimeError(
                "The local writing model server disconnected during generation. "
                "EmberWriter can restart Ollama from the Performance panel."
            ) from exc

        content = "".join(pieces)
        if not content.strip():
            raise RuntimeError(f"Ollama returned an empty response from {effective_model}")

        studio = streaming_generation._is_studio_scene(messages)
        record_model_call(
            stage="studio-prose" if studio else "writer-prose",
            model=effective_model,
            context_tokens=context_tokens,
            performance_profile="fast" if _is_fast_model(effective_model) else "quality",
            payload=final_metrics,
            first_token_ms=first_token_ms,
            total_ms=(perf_counter() - call_started) * 1000.0,
        )
        return content


def install_local_model_stream_reliability() -> None:
    """Install the local Ollama cold-start aware streaming path exactly once."""
    global _INSTALLED
    if _INSTALLED:
        return

    from . import generation_reliability as reliability

    # generation_reliability owns the public streamed wrapper (sampling, word ceilings, model
    # routing). Replace only its low-level transport so those contracts remain intact.
    reliability._original_generate_streamed = generate_streamed_reliable
    reliability._route_adult_model = route_adult_model_stable

    # High-heat auto-escalation remains available as an explicit environment opt-in, but it is
    # unsafe as a default without GPU/VRAM evidence.
    os.environ.setdefault("EMBER_AUTO_INSTALL_HIGH_HEAT_MODEL", "0")
    _INSTALLED = True
