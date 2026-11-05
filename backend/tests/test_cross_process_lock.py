"""Verify the production resource lock across independent Windows processes."""
from __future__ import annotations

import asyncio
import multiprocessing
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


def _crashing_worker(ready) -> None:
    async def go():
        async with reservation():
            ready.put("locked")
            await asyncio.sleep(60)
    asyncio.run(go())


def test_resource_lock_recovers_after_hard_process_termination():
    """The OS must release a held production lock after an unclean exit."""
    context = multiprocessing.get_context("spawn")
    ready = context.Queue()
    holder = context.Process(target=_crashing_worker, args=(ready,))
    holder.start()
    try:
        assert ready.get(timeout=10) == "locked"
        holder.terminate()
        holder.join(10)
        assert holder.exitcode is not None
        results = context.Queue()
        successor = context.Process(target=_worker, args=(results, 0.01))
        successor.start()
        try:
            successor.join(10)
            assert successor.exitcode == 0, "Surviving server could not reclaim the production lock"
            start, finish = results.get(timeout=3)
            assert finish >= start
        finally:
            if successor.is_alive():
                successor.terminate()
                successor.join(5)
            results.close()
    finally:
        if holder.is_alive():
            holder.terminate()
            holder.join(5)
        ready.close()
