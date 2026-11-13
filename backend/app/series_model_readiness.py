"""Bounded, private local model readiness for optional story extraction.

This is a transport/service check, NOT evidence of story comprehension or
successful long-form generation. No source text is sent during health checks.
"""
from __future__ import annotations

import httpx

from . import series_vault as vault

LOOPBACK = "http://127.0.0.1:11434"


def model_readiness(series_id: str) -> dict:
    vault.series_detail(series_id)  # Verify the specific private Series Vault exists.
    try:
        with httpx.Client(timeout=httpx.Timeout(3.0, connect=1.25),
                          trust_env=False) as client:
            response = client.get(LOOPBACK + "/api/tags")
            response.raise_for_status()
            payload = response.json()
        models = [
            item["name"] for item in payload.get("models", [])
            if isinstance(item, dict) and isinstance(item.get("name"), str)
            and 1 <= len(item["name"]) <= 200
            and not item["name"].lower().endswith((":cloud", "-cloud"))
        ][:30]
        return {
            "status": "available" if models else "no_installed_local_models",
            "models": models, "endpoint": "local_only",
            "source_text_sent": False, "generation_tested": False,
            "next_step": ("Select a model for a small, explicitly selected source passage." if models else
                           "Install a local model or use offline evidence and manual review."),
        }
    except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError,
            ValueError, TypeError, KeyError) as exc:
        timed_out = isinstance(exc, httpx.TimeoutException)
        return {
            "status": "timed_out" if timed_out else "unavailable",
            "models": [], "endpoint": "local_only",
            "source_text_sent": False, "generation_tested": False,
            "next_step": "Model access is unavailable. Source research and author review still work offline.",
        }
