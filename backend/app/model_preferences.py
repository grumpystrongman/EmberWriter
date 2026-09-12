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
