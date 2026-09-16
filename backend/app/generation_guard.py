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
_ACTIVE_GENERATIONS: dict[str, asyncio.Task[Response]] = {}


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


def cancel_generation(slug: str) -> bool:
    task = _ACTIVE_GENERATIONS.get(slug)
    if task is None or task.done():
        return False
    task.cancel()
    return True


async def guard_generation_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Bound Writer generation and expose the running task to the cancel endpoint."""
    match = _GENERATION_PATH.fullmatch(request.url.path)
    if request.method.upper() != "POST" or match is None:
        return await call_next(request)

    slug = match.group(1)
    existing = _ACTIVE_GENERATIONS.get(slug)
    if existing is not None and not existing.done():
        return JSONResponse(
            status_code=409,
            content={"detail": "A generation is already running for this project. Cancel it before starting another."},
        )

    task = asyncio.create_task(call_next(request), name=f"ember-generation:{slug}")
    _ACTIVE_GENERATIONS[slug] = task
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
        # The explicit cancel endpoint cancels the task being awaited here. Returning a
        # normal response lets the UI leave its busy state immediately instead of hanging.
        return JSONResponse(status_code=499, content={"detail": "Generation cancelled"})
    finally:
        if _ACTIVE_GENERATIONS.get(slug) is task:
            _ACTIVE_GENERATIONS.pop(slug, None)
