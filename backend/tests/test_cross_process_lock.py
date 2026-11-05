"""Verify the production resource lock across independent Windows processes."""
from __future__ import annotations

import asyncio
import multiprocessing
import queue
import time

from app.local_resources import reservation


def _worker(results, hold_seconds: float) -> None:
    async def go():
        async with reservation():
            entered = time.monotonic()
            await asyncio.sleep(hold_seconds)
            departed = time.monotonic()
            results.put((entered, departed))
    asyncio.run(go())


def test_host_level_resource_governor_serializes_processes():
    context = multiprocessing.get_context("spawn")
    events = context.Queue()
    first = context.Process(target=_worker, args=(events, 0.45))
    second = context.Process(target=_worker, args=(events, 0.45))
    first.start()
    second.start()
    try:
        first.join(15)
        second.join(15)
        assert first.exitcode == 0
        assert second.exitcode == 0
        intervals = sorted((events.get(timeout=3), events.get(timeout=3)))
        assert intervals[1][0] >= intervals[0][1] - 0.02
    finally:
        first.join(timeout=1)
        second.join(timeout=1)
        events.close()
