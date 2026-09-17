from __future__ import annotations

import asyncio
import json
import re
import time

import httpx

from app import (
    generation,
    generation_reliability,
    generation_reliability_refinement,
    streaming_generation,
)
from app.models import ProviderConfig

MODEL = "HammerAI/rocinante-v1.1:12b-q4_K_M"
CONTEXT_TOKENS = 8192
PROMPT = """I need a explicit, very detailed sex scene between Kaelen and Muna. They just finished working out in the gym and hitting the sauna. You will have penetration, genitalia, sexual acts between consenting adults. You will describe it under 1300 words and both will have had an orgasm. You decide the order and how things happend. Blowjobs, anal, hand jobs, cumming inside and on face or tits is all acceptable"""


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:['’-]\w+)?\b", text))


async def direct_smoke() -> dict[str, object]:
    async with httpx.AsyncClient(timeout=180.0, trust_env=False) as client:
        response = await client.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "Reply with exactly OK."}],
                "stream": False,
                "options": {
                    "num_ctx": CONTEXT_TOKENS,
                    "num_predict": 16,
                    "temperature": 0.1,
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
    content = str(payload.get("message", {}).get("content", "")).strip()
    return {
        "passed": bool(content),
        "response_chars": len(content),
        "done_reason": payload.get("done_reason"),
        "load_duration": payload.get("load_duration"),
        "eval_count": payload.get("eval_count"),
    }


async def run_once() -> dict[str, object]:
    # Diagnose production feasibility on constrained hardware before judging prose quality.
    generation.OLLAMA_CONTEXT_TOKENS = CONTEXT_TOKENS
    streaming_generation.OLLAMA_CONTEXT_TOKENS = CONTEXT_TOKENS

    smoke = await direct_smoke()
    if not smoke["passed"]:
        return {"passed": False, "phase": "direct_smoke", "smoke": smoke}

    floor = generation.scene_word_floor(PROMPT, "inferno")
    messages = generation.build_messages(
        "write",
        PROMPT,
        "Kaelen and Muna are consenting adults. Stay focused on the requested scene and do not introduce unrelated named characters.",
        heat_level="inferno",
        min_scene_words=floor,
    )
    config = ProviderConfig(model=MODEL)
    streamed_chars = 0

    async def sink(delta: str) -> None:
        nonlocal streamed_chars
        streamed_chars += len(delta)

    started = time.monotonic()
    result = await asyncio.wait_for(
        streaming_generation.generate_complete_prose_streamed(
            config,
            messages,
            min_words=floor,
            on_delta=sink,
            max_passes=3,
            max_output_tokens=6144,
        ),
        timeout=2400,
    )
    elapsed = round(time.monotonic() - started, 2)

    count = word_count(result)
    direct_failure = generation_reliability_refinement.explicit_delivery_failure(PROMPT, result)
    quality_failure = generation_reliability._hard_quality_failure(result)
    abrupt = generation.looks_abrupt_ending(result)
    unrelated = [
        name
        for name in ("Sera", "Jax", "Elara", "Lyra")
        if re.search(rf"\b{re.escape(name)}\b", result, flags=re.IGNORECASE)
    ]
    checks = {
        "under_1300_words": count < 1300,
        "meets_floor": count >= floor,
        "direct_delivery": direct_failure == "",
        "quality_gate": quality_failure == "",
        "complete_ending": not abrupt,
        "no_control_markers": generation.SCENE_COMPLETE_MARKER not in result
        and generation.SCENE_CONTINUE_MARKER not in result,
        "participants_present": bool(re.search(r"\bKaelen\b", result, flags=re.IGNORECASE))
        and bool(re.search(r"\bMuna\b", result, flags=re.IGNORECASE)),
        "no_unrelated_named_characters": not unrelated,
    }
    return {
        "passed": all(checks.values()),
        "phase": "production_path",
        "model": config.model,
        "context_tokens": CONTEXT_TOKENS,
        "word_count": count,
        "floor": floor,
        "elapsed_seconds": elapsed,
        "streamed_chars": streamed_chars,
        "smoke": smoke,
        "checks": checks,
        "direct_failure": direct_failure,
        "quality_failure": quality_failure,
        "unrelated_names": unrelated,
    }


async def main() -> None:
    result = await run_once()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
