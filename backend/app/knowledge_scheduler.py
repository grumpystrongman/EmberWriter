from __future__ import annotations

import asyncio
import logging
import os

from .knowledge import refresh_due_sources

DEFAULT_INTERVAL_SECONDS = 6 * 60 * 60
DEFAULT_INITIAL_DELAY_SECONDS = 20
LOGGER = logging.getLogger(__name__)


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(1, value)


async def knowledge_refresh_loop() -> None:
    """Refresh only sources whose manifest cadence says they are due.

    Network or source failures are recorded by the refresh layer and retried later. An unexpected scheduler
    failure is logged here but must never terminate the authoring service or discard last-known-good rules.
    """

    initial_delay = _positive_int(
        "EMBER_KNOWLEDGE_INITIAL_DELAY_SECONDS", DEFAULT_INITIAL_DELAY_SECONDS
    )
    interval = _positive_int("EMBER_KNOWLEDGE_REFRESH_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)
    await asyncio.sleep(initial_delay)
    while True:
        try:
            await refresh_due_sources()
        except Exception:  # noqa: BLE001 - scheduler must remain alive after unexpected source failures
            LOGGER.exception("Scheduled knowledge refresh failed")
        await asyncio.sleep(interval)
