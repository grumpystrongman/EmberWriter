"""Cooperative process-local resource slot for author-driven heavy work.

One long local model or offline narrator runs at a time within a server
event loop. Not a distributed lock: multiple Python server processes are
not safe as a single resource governor. Cancellation releases reservations.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from weakref import WeakKeyDictionary

_SLOTS: WeakKeyDictionary = WeakKeyDictionary()
_WAITING: WeakKeyDictionary = WeakKeyDictionary()


def _slot() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    if loop not in _SLOTS:
        _SLOTS[loop] = asyncio.Semaphore(1)
    return _SLOTS[loop]


def status() -> dict:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return {"scope": "single_server_process", "busy": False, "waiting": 0}
    slot = _slot()
    return {"scope": "single_server_process", "busy": slot.locked(),
            "waiting": _WAITING.get(loop, 0)}


@asynccontextmanager
async def reservation():
    loop = asyncio.get_running_loop()
    sem = _slot()
    _WAITING[loop] = _WAITING.get(loop, 0) + 1
    try:
        await sem.acquire()
    finally:
        _WAITING[loop] = max(0, _WAITING.get(loop, 1) - 1)
    try:
        yield
    finally:
        sem.release()
