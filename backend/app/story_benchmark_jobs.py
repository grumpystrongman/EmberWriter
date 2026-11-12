"""Explicit local-only synthetic model benchmark jobs for the author studio.

Never schedules a model automatically. Report storage is within the local Series
Vault root, and all prompts are synthetic. The caller's manuscript is never read.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import threading
from pathlib import Path
from uuid import uuid4

from . import series_vault as vault
from .story_generation_eval import run_benchmark

_guard = threading.Lock()
_active: set[str] = set()


def _path(series_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", series_id):
        raise ValueError("Invalid series identifier")
    vault.series_detail(series_id)
    root = vault._root() / "model-evaluations"
    root.mkdir(exist_ok=True)
    return root / f"{series_id}.json"


def _read(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


def _save(path: Path, payload: dict) -> None:
    tmp = path.with_name(f".{path.stem}-{uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def status(series_id: str) -> dict:
    path = _path(series_id)
    report = _read(path)
    if not report:
        return {"status": "not_run", "local_only": True}
    with _guard:
        alive = series_id in _active
    if report.get("status") in {"running", "queued"} and not alive:
        return {**report, "status": "interrupted",
                "error": "The local model process was interrupted. You can start again."}
    return report


def queue(series_id: str, model: str) -> dict:
    if not model.strip() or len(model) > 200:
        raise ValueError("Choose an installed local Ollama model")
    if re.search(r"(?:^|[-:])(cloud|remote)(?:$|[-:])", model, re.I):
        raise ValueError("Cloud model aliases are not allowed")
    path = _path(series_id)
    with _guard:
        if series_id in _active:
            raise ValueError("A local model evaluation is already running for this series")
        _active.add(series_id)
    job = {
        "status": "queued", "id": uuid4().hex, "model": model,
        "local_only": True, "synthetic_prompts": True,
    }
    try:
        _save(path, job)
    except Exception:
        with _guard:
            _active.discard(series_id)
        raise
    return job


async def execute(series_id: str, model: str) -> None:
    path = _path(series_id)
    queued = _read(path)
    try:
        _save(path, {**queued, "status": "running", "completed_scenarios": 0, "total_scenarios": 3})
        def progress(completed: int, total: int, report: dict) -> None:
            _save(path, {**queued, "status": "running", "completed_scenarios": completed,
                         "total_scenarios": total, "latest_scenario": {
                             "name": report["name"], "passed": report["passed"]}})
        result = await run_benchmark(model, on_progress=progress)
        _save(path, {**queued, "status": "completed", "result": result})
    except Exception as exc:
        # Do not store model output or user data inside errors.
        _save(path, {**queued, "status": "failed", "error": str(exc)[:500]})
    finally:
        with _guard:
            _active.discard(series_id)
