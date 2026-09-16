from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable

import httpx

from .generation import (
    MODEL_GATE,
    SCENE_COMPLETE_MARKER,
    SCENE_CONTINUE_MARKER,
)
from .models import ProviderConfig
from .ollama_runtime import choose_installed_model, installed_ollama_models

DeltaCallback = Callable[[str], Awaitable[None]]
StatusCallback = Callable[[str], Awaitable[None]]
_MARKER_HOLDBACK = max(len(SCENE_COMPLETE_MARKER), len(SCENE_CONTINUE_MARKER)) + 24


def _openai_chat_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:['’-]\w+)?\b", text))


def _strip_scene_markers(text: str) -> tuple[str, bool, bool]:
    complete = SCENE_COMPLETE_MARKER in text
    wants_more = SCENE_CONTINUE_MARKER in text
    cleaned = text.replace(SCENE_COMPLETE_MARKER, "").replace(SCENE_CONTINUE_MARKER, "").strip()
    return cleaned, complete, wants_more


async def generate_streamed(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    on_delta: DeltaCallback,
    temperature: float = 0.9,
    top_p: float = 0.95,
    json_mode: bool = False,
    max_output_tokens: int | None = None,
) -> str:
    """Generate while forwarding model text as it arrives.

    The ordinary generation path intentionally remains available for background tools and
    compatibility. This path is for interactive UI work where an author must be able to see
    that the model is actually producing text instead of staring at an empty spinner.
    """
    if not config.model.strip():
        raise ValueError("Choose a model before generating")

    async with MODEL_GATE:
        if config.provider == "ollama":
            installed = await installed_ollama_models(config.base_url)
            effective_model = choose_installed_model(config.model, installed)
            if not effective_model:
                raise RuntimeError(
                    "Ollama is running, but no local writing models are installed. "
                    "EmberWriter did not delete or replace a model; the Ollama library is empty."
                )
            if effective_model != config.model:
                config.model = effective_model

            options: dict[str, float | int] = {"temperature": temperature, "top_p": top_p}
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
            timeout = httpx.Timeout(connect=15.0, read=300.0, write=120.0, pool=15.0)
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
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise RuntimeError(
                                "Ollama returned an invalid streaming response"
                            ) from exc
                        if payload.get("error"):
                            raise RuntimeError(f"Ollama generation failed: {payload['error']}")
                        piece = str(payload.get("message", {}).get("content", ""))
                        if piece:
                            pieces.append(piece)
                            await on_delta(piece)
            except httpx.ReadTimeout as exc:
                raise RuntimeError(
                    "The local writing model stopped sending output for 5 minutes and "
                    "EmberWriter ended the stalled request."
                ) from exc
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    "The local writing model server disconnected during generation. "
                    "EmberWriter will restart Ollama automatically on the next request."
                ) from exc

            content = "".join(pieces)
            if not content.strip():
                raise RuntimeError(f"Ollama returned an empty response from {effective_model}")
            return content

        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        request_body: dict = {
            "model": config.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
        }
        if max_output_tokens is not None:
            request_body["max_tokens"] = max_output_tokens

        pieces: list[str] = []
        timeout = httpx.Timeout(connect=15.0, read=300.0, write=60.0, pool=15.0)
        async with (
            httpx.AsyncClient(timeout=timeout) as client,
            client.stream(
                "POST",
                _openai_chat_url(config.base_url),
                headers=headers,
                json=request_body,
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = payload.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                piece = str(delta.get("content", "") or "")
                if piece:
                    pieces.append(piece)
                    await on_delta(piece)

        content = "".join(pieces)
        if not content.strip():
            raise RuntimeError("Model returned no streamed text")
        return content


class _MarkerFilter:
    """Keep control markers out of the visible author-facing stream."""

    def __init__(self, emit: DeltaCallback) -> None:
        self._emit = emit
        self._pending = ""

    async def feed(self, piece: str) -> None:
        self._pending += piece
        if len(self._pending) <= _MARKER_HOLDBACK:
            return
        safe = self._pending[:-_MARKER_HOLDBACK]
        self._pending = self._pending[-_MARKER_HOLDBACK:]
        safe = safe.replace(SCENE_COMPLETE_MARKER, "").replace(SCENE_CONTINUE_MARKER, "")
        if safe:
            await self._emit(safe)

    async def finish(self) -> None:
        safe = self._pending.replace(SCENE_COMPLETE_MARKER, "").replace(SCENE_CONTINUE_MARKER, "")
        self._pending = ""
        if safe:
            await self._emit(safe)


async def generate_complete_prose_streamed(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    min_words: int,
    on_delta: DeltaCallback,
    on_status: StatusCallback | None = None,
    max_passes: int = 4,
    max_output_tokens: int = 6144,
) -> str:
    """Generate a complete scene while making every pass visible as it is written."""
    accumulated = ""
    working_messages = list(messages)

    for pass_index in range(max_passes):
        if on_status is not None:
            label = (
                "Writing scene…"
                if pass_index == 0
                else f"Continuing scene · pass {pass_index + 1}…"
            )
            await on_status(label)
        if pass_index > 0:
            await on_delta("\n\n")

        marker_filter = _MarkerFilter(on_delta)
        raw = await generate_streamed(
            config,
            working_messages,
            on_delta=marker_filter.feed,
            max_output_tokens=max_output_tokens,
        )
        await marker_filter.finish()

        cleaned, complete, wants_more = _strip_scene_markers(raw)
        if cleaned:
            accumulated = f"{accumulated}\n\n{cleaned}".strip()

        words = _word_count(accumulated)
        if complete and words >= min_words:
            return accumulated
        if words >= min_words and not wants_more and pass_index > 0:
            return accumulated
        if pass_index == max_passes - 1:
            return accumulated

        remaining = max(min_words - words, 0)
        continuation_instruction = (
            "Continue the SAME scene seamlessly from the exact final line above. Do not restart, recap, "
            "repeat earlier beats, change POV, or jump to a different scene. Finish the author's requested "
            "scene objective and its immediate consequence."
        )
        if remaining:
            continuation_instruction += (
                f" The draft is still roughly {remaining} words short of the requested scene floor."
            )
        continuation_instruction += (
            f" End with {SCENE_COMPLETE_MARKER} only after the scene has genuinely concluded; otherwise end with "
            f"{SCENE_CONTINUE_MARKER}."
        )
        working_messages = [
            *messages,
            {"role": "assistant", "content": accumulated},
            {"role": "user", "content": continuation_instruction},
        ]

    return accumulated
