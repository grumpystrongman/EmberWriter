from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

_GENERATION_PATH = re.compile(r"^/api/projects/([^/]+)/generate$")
_DEFAULT_TIMEOUT_SECONDS = 600.0
_ACTIVE_GENERATIONS: dict[str, asyncio.Task[object]] = {}


def generation_timeout_seconds() -> float:
    """Return the wall-clock budget for one Writer generation request.

    This is intentionally a total request budget, not a per-model-call budget. A complete
    scene may use several model passes plus Craft Pass; without a total cap those individual
    waits can compound into an hour-long spinner.
    """
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

    # The cancel endpoint is currently a synchronous FastAPI route and may execute in a
    # worker thread. Schedule cancellation on the task's owning event loop instead of
    # mutating an asyncio.Task from the wrong thread.
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


async def guard_generation_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Bound ordinary JSON Writer generation and expose it to the cancel endpoint."""
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
                    "Generation reached EmberWriter's total time limit and was stopped so the Writer cannot hang indefinitely. "
                    "The local model may need a smaller/faster model, fewer context files, or another Generate pass."
                )
            },
        )
    except asyncio.CancelledError:
        return JSONResponse(status_code=499, content={"detail": "Generation cancelled"})
    finally:
        unregister_generation_task(slug, task)
