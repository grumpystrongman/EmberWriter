from __future__ import annotations

import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / ".ember" / "local-models.json"


def preferred_local_model() -> str:
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    value = payload.get("preferred_model", "")
    return str(value).strip() if value else ""


def local_model_preferences() -> dict[str, str]:
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    keys = (
        "preferred_model",
        "adult_model",
        "accepted_adult_model",
        "quality_model",
        "fast_model",
        "high_heat_model",
    )
    return {
        key: str(payload.get(key) or "").strip()
        for key in keys
        if str(payload.get(key) or "").strip()
    }
