from __future__ import annotations

import asyncio
import json
import os

import httpx

from . import streaming_generation
from .generation import MODEL_GATE, OLLAMA_CONTEXT_TOKENS
from .models import ProviderConfig
from .ollama_runtime import choose_installed_model, installed_ollama_models

_FIRST_TOKEN_TIMEOUT_SECONDS = 15 * 60
_INTER_TOKEN_TIMEOUT_SECONDS = 5 * 60
_LARGE_MODEL_CONTEXT_TOKENS = 16384
_LARGE_MODEL_HINTS = ("cydonia", "24b", "24-b", "24_b")
_HERETIC_ROCINANTE = "hf.co/mradermacher/Rocinante-X-12B-v1-Heretic-Uncensored-GGUF:Q4_K_M"
_STANDARD_ROCINANTE = "HammerAI/rocinante-v1.1:12b-q4_K_M"
_HIGH_HEAT_CYDONIA = "Fermi/Cydonia-24B-v4.3-heretic-vision:Q4_K_M"

_ORIGINAL_GENERATE_STREAMED = streaming_generation.generate_streamed
_INSTALLED = False


def ollama_context_tokens_for(model: str) -> int:
    """Use a smaller prompt window for heavier local models to reduce cold-start pressure."""
    lowered = model.casefold()
    if any(hint in lowered for hint in _LARGE_MODEL_HINTS):
        return min(OLLAMA_CONTEXT_TOKENS, _LARGE_MODEL_CONTEXT_TOKENS)
    return OLLAMA_CONTEXT_TOKENS


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

    installed = await installed_ollama_models(config.base_url)
    if not installed:
        return

    current = next(
        (item for item in installed if item.casefold() == config.model.casefold()),
        None,
    )
    if current and reliability.adult_model_score(current) > 0:
        config.model = current
        return

    # Repair toward the 12B managed baseline first. The 24B tier is deliberately opt-in;
    # system RAM and disk alone are not enough to prove that a machine can infer it well.
    preferred = (
        _HERETIC_ROCINANTE,
        _STANDARD_ROCINANTE,
        _HIGH_HEAT_CYDONIA,
        "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m",
        "R4C3R/qwen3-8b-heretic:q4_k_m",
    )
    installed_by_name = {item.casefold(): item for item in installed}
    for candidate in preferred:
        resolved = installed_by_name.get(candidate.casefold())
        if resolved:
            config.model = resolved
            return

    ranked = sorted(installed, key=reliability.adult_model_score, reverse=True)
    if ranked and reliability.adult_model_score(ranked[0]) > 0:
        config.model = ranked[0]


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
    """Ollama stream path with separate cold-start and inter-token watchdogs."""
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

        options: dict[str, float | int] = {
            "temperature": temperature,
            "top_p": top_p,
            "num_ctx": ollama_context_tokens_for(effective_model),
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
        # Disable httpx's fixed per-read watchdog and apply our own state-aware timer below.
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
                            "rerun install.ps1 with the default auto tier to select the 12B baseline."
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
                    piece = str(payload.get("message", {}).get("content", ""))
                    if piece:
                        saw_text = True
                        pieces.append(piece)
                        await on_delta(piece)
        except httpx.ConnectError as exc:
            raise RuntimeError(
                "The local writing model server disconnected during generation. "
                "EmberWriter will restart Ollama automatically on the next request."
            ) from exc

        content = "".join(pieces)
        if not content.strip():
            raise RuntimeError(f"Ollama returned an empty response from {effective_model}")
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
