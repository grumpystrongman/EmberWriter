from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from .models import ProviderConfig
from .routes_performance import performance_status, restart_ollama, warm_model

_GENERATION_PATH = re.compile(r"^/api/projects/([^/]+)/generate$")
# Local generation now has meaningful phase-level safeguards: the Ollama stream has a 15-minute
# first-token watchdog and a 5-minute inter-token watchdog, while the Studio semantic verifier has
# its own bounded 10-minute read timeout. A short aggregate wall-clock deadline can therefore kill
# a healthy request simply because multiple valid phases ran sequentially. Keep only a distant
# six-hour emergency ceiling for pathological orchestration bugs; it is not a performance target.
_DEFAULT_TIMEOUT_SECONDS = 6 * 60 * 60.0
_ACTIVE_GENERATIONS: dict[str, asyncio.Task[object]] = {}


def generation_timeout_seconds() -> float:
    """Return the emergency wall-clock ceiling for one Writer generation request."""
    raw = os.getenv("EMBER_GENERATION_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT_SECONDS)).strip()
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_TIMEOUT_SECONDS
    return max(0.01, value)


def generation_is_active(slug: str) -> bool:
    task = _ACTIVE_GENERATIONS.get(slug)
    return task is not None and not task.done()


def register_generation_task(slug: str, task: asyncio.Task[object]) -> bool:
    existing = _ACTIVE_GENERATIONS.get(slug)
    if existing is not None and not existing.done():
        return False
    _ACTIVE_GENERATIONS[slug] = task
    return True


def unregister_generation_task(slug: str, task: asyncio.Task[object]) -> None:
    if _ACTIVE_GENERATIONS.get(slug) is task:
        _ACTIVE_GENERATIONS.pop(slug, None)


def cancel_generation(slug: str) -> bool:
    task = _ACTIVE_GENERATIONS.get(slug)
    if task is None or task.done():
        return False

    loop = task.get_loop()
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None
    if running_loop is loop:
        task.cancel()
    else:
        loop.call_soon_threadsafe(task.cancel)
    return True


async def _performance_api(request: Request) -> Response | None:
    """Serve local diagnostics without coupling app startup to another router import list."""
    path = request.url.path.rstrip("/")
    try:
        if request.method.upper() == "GET" and path == "/api/performance":
            return JSONResponse(content=performance_status())
        if request.method.upper() == "POST" and path == "/api/performance/warm":
            payload = ProviderConfig.model_validate(await request.json())
            return JSONResponse(content=await warm_model(payload))
        if request.method.upper() == "POST" and path == "/api/performance/restart-ollama":
            return JSONResponse(content=await restart_ollama())
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    except (ValueError, TypeError) as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    return None


async def guard_generation_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Expose performance controls and guard ordinary JSON Writer generation."""
    performance_response = await _performance_api(request)
    if performance_response is not None:
        return performance_response

    match = _GENERATION_PATH.fullmatch(request.url.path)
    if request.method.upper() != "POST" or match is None:
        return await call_next(request)

    slug = match.group(1)
    task = asyncio.create_task(call_next(request), name=f"ember-generation:{slug}")
    if not register_generation_task(slug, task):
        task.cancel()
        return JSONResponse(
            status_code=409,
            content={"detail": "A generation is already running for this project. Cancel it before starting another."},
        )

    try:
        return await asyncio.wait_for(task, timeout=generation_timeout_seconds())
    except TimeoutError:
        if not task.done():
            task.cancel()
        return JSONResponse(
            status_code=504,
            content={
                "detail": (
                    "Generation reached EmberWriter's emergency total safety ceiling. "
                    "Check the Performance panel for the phase and local-model telemetry that consumed the time."
                )
            },
        )
    except asyncio.CancelledError:
        return JSONResponse(status_code=499, content={"detail": "Generation cancelled"})
    finally:
        unregister_generation_task(slug, task)
