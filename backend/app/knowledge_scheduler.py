from __future__ import annotations

import asyncio
import os

from .knowledge import refresh_due_sources

DEFAULT_INTERVAL_SECONDS = 6 * 60 * 60
DEFAULT_INITIAL_DELAY_SECONDS = 20


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(1, value)


async def knowledge_refresh_loop() -> None:
    """Refresh only sources whose manifest cadence says they are due.

    The loop is deliberately conservative: network failures are recorded on the source and retried on the
    next scheduler interval, while the last successful/seeded rules remain available offline.
    """

    initial_delay = _positive_int(
        "EMBER_KNOWLEDGE_INITIAL_DELAY_SECONDS", DEFAULT_INITIAL_DELAY_SECONDS
    )
    interval = _positive_int("EMBER_KNOWLEDGE_REFRESH_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)
    await asyncio.sleep(initial_delay)
    while True:
        try:
            await refresh_due_sources()
        except Exception:  # noqa: BLE001 - scheduler must never take down the authoring service
            pass
        await asyncio.sleep(interval)
