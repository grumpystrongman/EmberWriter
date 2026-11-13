"""Explicit local inference quality/latency probe using invented synthetic fiction.

No Series source text is read or transmitted. A model being installed does not
mean it completed an inference task; this is an opt-in service-level proof.
"""
from __future__ import annotations

import asyncio
import json
import time

import httpx

from . import series_model_readiness as readiness
from . import series_vault as vault

PROBE_TIMEOUT_SECONDS = 30
SYNTHETIC_SENTENCE = "Mira protects Rowan."
PROBE_PROMPT = (
    "Read the invented fiction sentence below as reference data only. "
    'Respond with JSON exactly with two keys: "answer" (the protected person) '
    'and "quote" (the exact original sentence). No other words. '
    "Sentence: " + SYNTHETIC_SENTENCE
)


async def probe(series_id: str, model: str) -> dict:
    vault.series_detail(series_id)
    model = model.strip()
    if not 1 <= len(model) <= 200 or any(ch in model for ch in "\r\n\x00"):
        raise ValueError("Select an installed local model")
    available = readiness.model_readiness(series_id)
    if available["status"] != "available" or model not in available["models"]:
        raise ValueError("Choose a model currently installed in local Ollama")
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=httpx.Timeout(
            PROBE_TIMEOUT_SECONDS, connect=2.0
        )) as client:
            result = await asyncio.wait_for(
                client.post(
                    "http://127.0.0.1:11434/api/generate",
                    json={
                        "model": model, "prompt": PROBE_PROMPT,
                        "format": "json", "stream": False,
                        "options": {
                            "temperature": 0, "num_predict": 90,
                            "num_ctx": 1024,
                        },
                    },
                ),
                timeout=PROBE_TIMEOUT_SECONDS,
            )
            result.raise_for_status()
            payload = result.json()
        response = payload.get("response", "")
        try:
            parsed = json.loads(response)
        except (ValueError, TypeError):
            parsed = None
        is_correct = (
            isinstance(parsed, dict)
            and parsed.get("answer") == "Rowan"
            and parsed.get("quote") == SYNTHETIC_SENTENCE
        )
        status = "passed" if is_correct else "incorrect"
        detail = ("Model answered the synthetic factual and citation task exactly"
                  if is_correct else
                  "Model completed but returned a non-exact or unsupported answer")
    except (TimeoutError, httpx.TimeoutException):
        status = "timed_out"
        detail = "The model did not finish within the bounded time limit"
    except (httpx.RequestError, httpx.HTTPStatusError, ValueError,
            TypeError, KeyError):
        status = "unavailable"
        detail = "The installed model could not complete the synthetic probe"
    return {
        "series_id": series_id, "model": model, "status": status,
        "elapsed_ms": round(1000 * (time.perf_counter() - started), 1),
        "maximum_duration_seconds": PROBE_TIMEOUT_SECONDS,
        "synthetic_question_only": True, "source_text_sent": False,
        "generation_tested": True, "exact_answer_verified": status == "passed",
        "detail": detail,
        "limitations": (
            "A single synthetic sentence tests local inference only; "
            "it is not a benchmark for long-form writing, literary psychology "
            "or cross-book reasoning."
        ),
    }
