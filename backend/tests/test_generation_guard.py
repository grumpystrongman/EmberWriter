from __future__ import annotations

import asyncio
from types import SimpleNamespace

from app.generation_guard import cancel_generation, guard_generation_request


def _request(slug: str = "test-project"):
    return SimpleNamespace(
        method="POST",
        url=SimpleNamespace(path=f"/api/projects/{slug}/generate"),
    )


def test_generation_guard_times_out_total_request(monkeypatch):
    monkeypatch.setenv("EMBER_GENERATION_TIMEOUT_SECONDS", "0.02")
    cancelled = False

    async def slow_call_next(_request):
        nonlocal cancelled
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled = True
            raise

    async def exercise():
        response = await guard_generation_request(_request(), slow_call_next)
        return response

    response = asyncio.run(exercise())
    assert response.status_code == 504
    assert cancelled is True


def test_generation_guard_can_be_cancelled_explicitly(monkeypatch):
    monkeypatch.setenv("EMBER_GENERATION_TIMEOUT_SECONDS", "5")
    started = asyncio.Event()
    cancelled = False

    async def slow_call_next(_request):
        nonlocal cancelled
        started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled = True
            raise

    async def exercise():
        guarded = asyncio.create_task(guard_generation_request(_request("cancel-me"), slow_call_next))
        await started.wait()
        assert cancel_generation("cancel-me") is True
        response = await guarded
        return response

    response = asyncio.run(exercise())
    assert response.status_code == 499
    assert cancelled is True
    assert cancel_generation("cancel-me") is False


def test_generation_guard_rejects_duplicate_project_generation(monkeypatch):
    monkeypatch.setenv("EMBER_GENERATION_TIMEOUT_SECONDS", "5")
    started = asyncio.Event()
    release = asyncio.Event()

    async def first_call_next(_request):
        started.set()
        await release.wait()
        return SimpleNamespace(status_code=200)

    async def duplicate_call_next(_request):
        raise AssertionError("duplicate generation should never reach the route")

    async def exercise():
        first = asyncio.create_task(guard_generation_request(_request("same-project"), first_call_next))
        await started.wait()
        duplicate = await guard_generation_request(_request("same-project"), duplicate_call_next)
        release.set()
        await first
        return duplicate

    response = asyncio.run(exercise())
    assert response.status_code == 409
