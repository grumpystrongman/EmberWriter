from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from .model_acceptance import run_model_acceptance

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_DIR = _REPO_ROOT / ".ember"
REPORT_PATH = _RUNTIME_DIR / "model-bakeoff.json"
LOCAL_MODELS_PATH = _RUNTIME_DIR / "local-models.json"

PYGMALION_3_12B = "hf.co/mradermacher/Pygmalion-3-12B-GGUF:Q4_K_M"
MAGNUM_V4_12B = "hf.co/mradermacher/magnum-v4-12b-GGUF:Q4_K_M"
DEFAULT_CANDIDATES = (PYGMALION_3_12B, MAGNUM_V4_12B)


def _score(report: dict[str, object]) -> tuple[int, int, int]:
    results = list(report.get("results") or [])
    passes = int(report.get("passes") or 0)
    total_words = sum(int(item.get("word_count") or 0) for item in results if isinstance(item, dict))
    failure_count = sum(len(item.get("failures") or []) for item in results if isinstance(item, dict))
    return (passes, -failure_count, total_words)


def choose_adult_model(reports: list[dict[str, object]]) -> str:
    eligible = [report for report in reports if report.get("passed") is True]
    if not eligible:
        return ""
    eligible.sort(key=_score, reverse=True)
    return str(eligible[0].get("requested_model") or "")


def _load_local_models() -> dict[str, object]:
    try:
        payload = json.loads(LOCAL_MODELS_PATH.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_local_models(payload: dict[str, object]) -> None:
    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_MODELS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


async def run_bakeoff(
    candidates: tuple[str, ...] = DEFAULT_CANDIDATES,
    *,
    base_url: str = "http://localhost:11434",
    attempts: int = 3,
) -> dict[str, object]:
    reports: list[dict[str, object]] = []
    for model in candidates:
        reports.append(
            await run_model_acceptance(
                model,
                base_url=base_url,
                attempts=attempts,
            )
        )

    adult_model = choose_adult_model(reports)
    result = {
        "updated_at": datetime.now(UTC).isoformat(),
        "purpose": "adult",
        "candidates": list(candidates),
        "winner": adult_model or None,
        "reports": reports,
    }

    _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if adult_model:
        config = _load_local_models()
        config["adult_model"] = adult_model
        config["accepted_adult_model"] = adult_model
        config["adult_model_acceptance_report"] = str(REPORT_PATH.relative_to(_REPO_ROOT))
        _save_local_models(config)

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run EmberWriter's local adult-scene model bakeoff and persist the best passing model"
    )
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--model", action="append", dest="models")
    args = parser.parse_args()

    candidates = tuple(args.models or DEFAULT_CANDIDATES)
    report = asyncio.run(
        run_bakeoff(
            candidates,
            base_url=args.base_url,
            attempts=args.attempts,
        )
    )
    print(json.dumps(report, indent=2))
    return 0 if report.get("winner") else 2


if __name__ == "__main__":
    raise SystemExit(main())
