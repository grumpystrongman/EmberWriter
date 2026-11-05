"""Process-safe local resource governor for expensive narration and model work.

An OS file lock prevents multiple EmberWriter server processes on the same
machine from starting expensive workloads simultaneously. A crash releases
the OS lock. This is intentionally not a distributed multi-host lock.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from weakref import WeakKeyDictionary

_SLOTS: WeakKeyDictionary = WeakKeyDictionary()
_WAITING: WeakKeyDictionary = WeakKeyDictionary()
_LOCK_PATH = Path(tempfile.gettempdir()) / "emberwriter-local-production.lock"


def _slot() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    if loop not in _SLOTS:
        _SLOTS[loop] = asyncio.Semaphore(1)
    return _SLOTS[loop]


def _open_lock():
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Append mode permits opening a persistent lock file without truncating a
    # byte another process may currently have locked.
    handle = open(_LOCK_PATH, "a+b", buffering=0)
    if os.name == "nt":
        if handle.tell() == 0:
            handle.write(b"\0")
        handle.seek(0)
    return handle


def _try_acquire(handle) -> bool:
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError as exc:
            # WinError 33/36 and EACCES mean another process owns the lock.
            if exc.errno in (13, 36) or getattr(exc, "winerror", None) in (33, 36):
                return False
            raise
    else:
        import fcntl
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False


def _release(handle) -> None:
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def status() -> dict:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return {"scope": "single_machine_cross_process", "busy": False, "waiting": 0}
    return {"scope": "single_machine_cross_process", "busy": _slot().locked(),
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
    handle = None
    acquired = False
    try:
        handle = _open_lock()
        while not acquired:
            acquired = _try_acquire(handle)
            if not acquired:
                await asyncio.sleep(0.1)
        yield
    finally:
        try:
            if handle is not None:
                if acquired:
                    _release(handle)
                handle.close()
        finally:
            sem.release()
