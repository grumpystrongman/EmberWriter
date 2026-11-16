"""Opt-in bounded streaming Ollama diagnostic using synthetic fiction only.

Measures first generated response text separately from total wall clock time.
No Series source text, source metadata or generated prose is stored. Cancellation
can be initiated by disconnecting an HTTP request (e.g. UI AbortController).
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable

import httpx

from . import series_model_readiness as readiness
from . import series_vault as vault
from .series_model_probe import PROBE_PROMPT, SYNTHETIC_SENTENCE

# Context managers depend on their outer client and deadline; they cannot be
# combined without constructing the stream before its client exists.
# ruff: noqa: SIM117

MAX_SECONDS = 45
MAX_STREAM_BYTES = 32_768
MAX_RESPONSE_CHARS = 8_192
MAX_EVENTS = 256
LOOPBACK_URL = "http://127.0.0.1:11434/api/generate"


async def _generate(model: str) -> dict:
    started = time.perf_counter()
    first_token_ms = None
    response_parts: list[str] = []
    response_chars = 0
    bytes_read = 0
    events = 0
    final: dict = {}
    done = False
    status = "incomplete"
    detail = "Local model stream ended without Ollama completion marker"
    try:
        async with asyncio.timeout(MAX_SECONDS):
            async with httpx.AsyncClient(
                trust_env=False, timeout=httpx.Timeout(
                    MAX_SECONDS, connect=3.0, read=MAX_SECONDS, write=5.0, pool=3.0
                ),
            ) as client:
                async with client.stream("POST", LOOPBACK_URL, json={
                    "model": model, "prompt": PROBE_PROMPT,
                    "format": "json", "stream": True, "keep_alive": "1m",
                    "options": {"temperature": 0, "num_predict": 100, "num_ctx": 1024},
                }) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        bytes_read += len(line.encode("utf-8"))
                        events += 1
                        if bytes_read > MAX_STREAM_BYTES or events > MAX_EVENTS:
                            status, detail = "response_limit", "Model stream exceeded bounded safety limits"
                            break
                        if not line.strip():
                            continue
                        payload = json.loads(line)
                        if not isinstance(payload, dict) or payload.get("error"):
                            status, detail = "unavailable", "Local Ollama returned a stream error"
                            break
                        part = payload.get("response", "")
                        if not isinstance(part, str):
                            status, detail = "unavailable", "Local model returned invalid response data"
                            break
                        if part and first_token_ms is None:
                            first_token_ms = round((time.perf_counter() - started) * 1000, 1)
                        response_chars += len(part)
                        if response_chars > MAX_RESPONSE_CHARS:
                            status, detail = "response_limit", "Model generated excessive output"
                            break
                        response_parts.append(part)
                        if payload.get("done") is True:
                            done, final = True, payload
                            break
        if done:
            try:
                answer = json.loads("".join(response_parts))
            except (ValueError, TypeError):
                answer = None
            valid = (
                isinstance(answer, dict)
                and answer.get("answer") == "Rowan"
                and answer.get("quote") == SYNTHETIC_SENTENCE
            )
            status = "passed" if valid else "incorrect"
            detail = ("Exact synthetic answer and quote verified"
                      if valid else "Completed response did not match the synthetic evidence")
    except (TimeoutError, httpx.TimeoutException):
        status, detail = "timed_out", "No complete model response within 45 seconds"
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError, TypeError):
        status, detail = "unavailable", "Local model stream failed before verification"
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    def ns_to_ms(key: str) -> float | None:
        value = final.get(key)
        return round(value / 1_000_000, 1) if isinstance(value, (float, int)) and value >= 0 else None
    generation_ms = ns_to_ms("eval_duration")
    generated_tokens = final.get("eval_count") if done else None
    tokens_per_second = (
        round(generated_tokens * 1000 / generation_ms, 1)
        if isinstance(generated_tokens, int) and not isinstance(generated_tokens, bool)
        and generation_ms is not None and generation_ms > 0 else None
    )
    return {
        "model": model, "status": status, "detail": detail,
        "elapsed_ms": elapsed_ms, "first_token_ms": first_token_ms,
        "load_ms": ns_to_ms("load_duration"),
        "prompt_eval_ms": ns_to_ms("prompt_eval_duration"),
        "generation_ms": generation_ms,
        "prompt_tokens": final.get("prompt_eval_count") if done else None,
        "generated_tokens": generated_tokens, "tokens_per_second": tokens_per_second,
        "stream_events": events, "stream_completed": done,
        "exact_answer_verified": status == "passed",
        "source_text_sent": False, "synthetic_question_only": True,
        "generation_tested": True, "maximum_duration_seconds": MAX_SECONDS,
        "limitations": (
            "Synthetic local transport and one factual quote only. "
            "Not a cross-book, writing-quality or chapter-reasoning benchmark."
        ),
    }


async def probe(
    series_id: str,
    model: str,
    *,
    is_disconnected: Callable[[], Awaitable[bool]] | None = None,
) -> dict:
    vault.series_detail(series_id)
    model = model.strip()
    if not 1 <= len(model) <= 200 or any(ch in model for ch in "\r\n\x00"):
        raise ValueError("Select an installed local model")
    ready = readiness.model_readiness(series_id)
    if ready["status"] != "available" or model not in ready["models"]:
        raise ValueError("Choose a model currently installed in local Ollama")
    task = asyncio.create_task(_generate(model))
    watcher = None
    if is_disconnected is not None:
        async def watch_disconnect() -> None:
            while not task.done():
                if await is_disconnected():
                    task.cancel()
                    return
                await asyncio.sleep(0.15)
        watcher = asyncio.create_task(watch_disconnect())
    try:
        return {"series_id": series_id, **await task}
    finally:
        if watcher is not None:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
