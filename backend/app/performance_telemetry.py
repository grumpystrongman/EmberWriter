from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from time import perf_counter
from uuid import uuid4

_LOCK = RLock()
_ACTIVE_GENERATION_ID: str | None = None
_ACTIVE_GENERATIONS: dict[str, dict[str, object]] = {}
_RECENT_CALLS: list[dict[str, object]] = []
_LAST_GENERATION: dict[str, object] | None = None
_MAX_RECENT_CALLS = 24


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_ms(payload: dict[str, object], key: str) -> float | None:
    value = payload.get(key)
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    return round(float(value) / 1_000_000.0, 1)


def _rate(count: object, duration_ns: object) -> float | None:
    if not isinstance(count, (int, float)) or not isinstance(duration_ns, (int, float)):
        return None
    if count <= 0 or duration_ns <= 0:
        return None
    return round(float(count) / (float(duration_ns) / 1_000_000_000.0), 2)


def begin_generation(
    *,
    kind: str,
    model: str,
    performance_profile: str,
    context_chars: int = 0,
) -> str:
    global _ACTIVE_GENERATION_ID
    generation_id = uuid4().hex
    with _LOCK:
        _ACTIVE_GENERATION_ID = generation_id
        _ACTIVE_GENERATIONS[generation_id] = {
            "id": generation_id,
            "kind": kind,
            "model": model,
            "performance_profile": performance_profile,
            "context_chars": context_chars,
            "started_at": _utc_now(),
            "started_perf": perf_counter(),
        }
    return generation_id


def update_generation_context(generation_id: str, context_chars: int) -> None:
    with _LOCK:
        active = _ACTIVE_GENERATIONS.get(generation_id)
        if active is not None:
            active["context_chars"] = int(max(context_chars, 0))


def record_model_call(
    *,
    stage: str,
    model: str,
    context_tokens: int,
    performance_profile: str,
    payload: dict[str, object] | None = None,
    first_token_ms: float | None = None,
    total_ms: float | None = None,
) -> dict[str, object]:
    metrics = payload or {}
    call: dict[str, object] = {
        "generation_id": _ACTIVE_GENERATION_ID,
        "stage": stage,
        "model": model,
        "performance_profile": performance_profile,
        "context_tokens": int(max(context_tokens, 0)),
        "first_token_ms": round(first_token_ms, 1) if first_token_ms is not None else None,
        "total_ms": round(total_ms, 1) if total_ms is not None else None,
        "load_ms": _duration_ms(metrics, "load_duration"),
        "prompt_eval_tokens": int(metrics.get("prompt_eval_count", 0) or 0),
        "prompt_eval_ms": _duration_ms(metrics, "prompt_eval_duration"),
        "prompt_tokens_per_second": _rate(
            metrics.get("prompt_eval_count"), metrics.get("prompt_eval_duration")
        ),
        "eval_tokens": int(metrics.get("eval_count", 0) or 0),
        "eval_ms": _duration_ms(metrics, "eval_duration"),
        "tokens_per_second": _rate(metrics.get("eval_count"), metrics.get("eval_duration")),
        "recorded_at": _utc_now(),
    }
    with _LOCK:
        _RECENT_CALLS.append(call)
        del _RECENT_CALLS[:-_MAX_RECENT_CALLS]
    return call


def finish_generation(
    generation_id: str,
    *,
    success: bool,
    partial: bool = False,
    error: str | None = None,
) -> dict[str, object] | None:
    global _ACTIVE_GENERATION_ID, _LAST_GENERATION
    with _LOCK:
        active = _ACTIVE_GENERATIONS.pop(generation_id, None)
        if active is None:
            return None
        if _ACTIVE_GENERATION_ID == generation_id:
            _ACTIVE_GENERATION_ID = None
        started_perf = float(active.pop("started_perf", perf_counter()))
        calls = [item for item in _RECENT_CALLS if item.get("generation_id") == generation_id]
        result: dict[str, object] = {
            **active,
            "finished_at": _utc_now(),
            "total_ms": round((perf_counter() - started_perf) * 1000.0, 1),
            "success": bool(success),
            "partial": bool(partial),
            "error": error,
            "calls": deepcopy(calls),
        }
        prose_calls = [item for item in calls if "prose" in str(item.get("stage", ""))]
        verifier_calls = [item for item in calls if "verifier" in str(item.get("stage", ""))]
        result["prose_total_ms"] = round(
            sum(float(item.get("total_ms") or 0.0) for item in prose_calls), 1
        )
        result["verifier_total_ms"] = round(
            sum(float(item.get("total_ms") or 0.0) for item in verifier_calls), 1
        )
        _LAST_GENERATION = result
        return deepcopy(result)


def snapshot() -> dict[str, object]:
    with _LOCK:
        active = None
        if _ACTIVE_GENERATION_ID:
            item = _ACTIVE_GENERATIONS.get(_ACTIVE_GENERATION_ID)
            if item:
                active = {key: value for key, value in item.items() if key != "started_perf"}
                active["elapsed_ms"] = round(
                    (perf_counter() - float(item.get("started_perf", perf_counter()))) * 1000.0,
                    1,
                )
        return {
            "active_generation": deepcopy(active),
            "last_generation": deepcopy(_LAST_GENERATION),
            "recent_calls": deepcopy(_RECENT_CALLS[-10:]),
        }


def reset_for_tests() -> None:
    global _ACTIVE_GENERATION_ID, _LAST_GENERATION
    with _LOCK:
        _ACTIVE_GENERATION_ID = None
        _ACTIVE_GENERATIONS.clear()
        _RECENT_CALLS.clear()
        _LAST_GENERATION = None
