from __future__ import annotations

import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BAKEOFF_REPORT_PATH = _REPO_ROOT / ".ember" / "writing-model-bakeoff.json"
_BAKEOFF_ACCEPTANCE_VERSION = 3

# Dedicated adult-fiction candidates. Keep these as capability-slot defaults rather than
# embedding them throughout Studio so EmberWriter can replace either model later without
# changing author-facing workflows.
PYGMALION_3_12B = "hf.co/PygmalionAI/Pygmalion-3-12B-GGUF:Q4_K_S"
MAGNUM_V4_12B = "hf.co/anthracite-org/magnum-v4-12b-gguf:Q4_K_M"
HERETIC_ROCINANTE_12B = "hf.co/mradermacher/Rocinante-X-12B-v1-Heretic-Uncensored-GGUF:Q4_K_M"
STANDARD_ROCINANTE_12B = "HammerAI/rocinante-v1.1:12b-q4_K_M"
FAST_ADULT_8B = "R4C3R/qwen3-8b-heretic:q4_k_m"
HIGH_HEAT_CYDONIA_24B = "Fermi/Cydonia-24B-v4.3-heretic-vision:Q4_K_M"

ADULT_EXPLICIT_CANDIDATES = (PYGMALION_3_12B, MAGNUM_V4_12B)

# Model-level licenses are recorded for product/UI attribution and release review. This does
# not assert that every upstream training example has independent commercial provenance.
MODEL_LICENSES: dict[str, str] = {
    PYGMALION_3_12B: "Apache-2.0",
    MAGNUM_V4_12B: "Apache-2.0",
}


def adult_model_score(model: str) -> int:
    """Rank installed models for direct adult-fiction delivery, not generic reasoning."""
    name = model.casefold()
    if "pygmalion-3-12b" in name:
        return 320
    if "magnum-v4-12b" in name:
        return 305
    if "cydonia" in name and any(token in name for token in ("heretic", "abliter", "decensor")):
        return 280
    if "rocinante-x" in name:
        return 270
    if "cydonia" in name:
        return 260
    if "rocinante" in name:
        return 250
    if any(token in name for token in ("magidonia", "magnum", "mag-mell", "mag_mell")):
        return 240
    if any(token in name for token in ("stheno", "pygmalion", "lunaris", "nemomix")):
        return 230
    if "qwen2.5-14b" in name and "heretic" in name:
        return 160
    if "qwen3-8b" in name and "heretic" in name:
        return 150
    if any(token in name for token in ("heretic", "uncensored", "abliterat")):
        return 125
    return 0


def _load_bakeoff_winner() -> str | None:
    try:
        payload = json.loads(_BAKEOFF_REPORT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("passed") is not True:
        return None
    if payload.get("acceptance_version") != _BAKEOFF_ACCEPTANCE_VERSION:
        return None
    requested = {str(value).casefold() for value in payload.get("models", []) if value}
    required = {value.casefold() for value in ADULT_EXPLICIT_CANDIDATES}
    if requested != required:
        return None
    winner = str(payload.get("best_model", "")).strip()
    return winner or None


def preferred_adult_model(installed: list[str]) -> str | None:
    """Resolve the best installed adult model, honoring a measured local bakeoff winner."""
    if not installed:
        return None
    by_name = {item.casefold(): item for item in installed}

    measured = _load_bakeoff_winner()
    if measured:
        resolved = by_name.get(measured.casefold())
        if resolved:
            return resolved

    for candidate in (
        *ADULT_EXPLICIT_CANDIDATES,
        HERETIC_ROCINANTE_12B,
        STANDARD_ROCINANTE_12B,
        FAST_ADULT_8B,
        HIGH_HEAT_CYDONIA_24B,
        "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m",
    ):
        resolved = by_name.get(candidate.casefold())
        if resolved:
            return resolved

    ranked = sorted(installed, key=adult_model_score, reverse=True)
    return ranked[0] if ranked and adult_model_score(ranked[0]) > 0 else None
