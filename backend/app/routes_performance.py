from __future__ import annotations

import asyncio
import os
import platform
import re
import shutil
import subprocess

import httpx
from fastapi import APIRouter, HTTPException

from .models import ProviderConfig
from .performance_telemetry import snapshot

router = APIRouter(prefix="/api/performance", tags=["performance"])


def _split_columns(line: str) -> list[str]:
    return [part.strip() for part in re.split(r"\s{2,}", line.strip()) if part.strip()]


def _ollama_processes() -> list[dict[str, str]]:
    executable = shutil.which("ollama")
    if not executable:
        return []
    try:
        completed = subprocess.run(
            [executable, "ps"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return []
    headers = [item.casefold().replace(" ", "_") for item in _split_columns(lines[0])]
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        values = _split_columns(line)
        if not values:
            continue
        row = {headers[index]: value for index, value in enumerate(values) if index < len(headers)}
        if "name" in row:
            rows.append(row)
    return rows


def _nvidia_gpus() -> list[dict[str, object]]:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return []
    try:
        completed = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total,memory.used,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    gpus: list[dict[str, object]] = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 4:
            continue
        try:
            gpus.append(
                {
                    "name": parts[0],
                    "memory_total_mb": int(parts[1]),
                    "memory_used_mb": int(parts[2]),
                    "utilization_percent": int(parts[3]),
                }
            )
        except ValueError:
            continue
    return gpus


def _performance_recommendations(models: list[dict[str, str]]) -> list[str]:
    recommendations: list[str] = []
    processors = [item.get("processor", "") for item in models]
    if not processors:
        recommendations.append("Warm the selected model to measure its CPU/GPU placement and remove cold-load latency.")
    elif any("100% CPU" in processor for processor in processors):
        recommendations.append("The loaded model is CPU-only. Fast 8B or a smaller context can materially improve speed if it enables GPU offload.")
    elif any("CPU" in processor and "GPU" in processor for processor in processors):
        recommendations.append("The loaded model is split across CPU and GPU. Fast 8B or a smaller context may let it fit fully in VRAM.")
    elif processors and all("100% GPU" in processor for processor in processors):
        recommendations.append("The loaded model is fully GPU-resident; focus next on prompt-evaluation size and generated token count.")

    if os.getenv("OLLAMA_FLASH_ATTENTION", "").strip() != "1":
        recommendations.append("Flash Attention is not enabled in EmberWriter's Ollama runtime. Use Restart Ollama tuned.")
    if os.getenv("OLLAMA_KV_CACHE_TYPE", "").strip().casefold() != "q8_0":
        recommendations.append("KV cache is not q8_0 in EmberWriter's Ollama runtime. Use Restart Ollama tuned.")
    return recommendations


@router.get("")
def performance_status() -> dict[str, object]:
    models = _ollama_processes()
    return {
        **snapshot(),
        "ollama": {
            "available": shutil.which("ollama") is not None,
            "loaded_models": models,
            "flash_attention": os.getenv("OLLAMA_FLASH_ATTENTION", ""),
            "kv_cache_type": os.getenv("OLLAMA_KV_CACHE_TYPE", "") or "f16/default",
            "num_parallel": os.getenv("OLLAMA_NUM_PARALLEL", "") or "1/default",
        },
        "gpus": _nvidia_gpus(),
        "platform": platform.system(),
        "recommendations": _performance_recommendations(models),
    }


@router.post("/warm")
async def warm_model(provider: ProviderConfig) -> dict[str, object]:
    if provider.provider != "ollama" or not provider.model.strip():
        raise HTTPException(status_code=400, detail="Choose a local Ollama model to warm")
    try:
        timeout = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.post(
                f"{provider.base_url.rstrip('/')}/api/generate",
                json={
                    "model": provider.model,
                    "prompt": "",
                    "stream": False,
                    "keep_alive": "30m",
                    "options": {"num_predict": 1},
                },
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Could not warm Ollama model: {exc}") from exc
    return {"ok": True, "model": provider.model, "loaded_models": _ollama_processes()}


@router.post("/restart-ollama")
async def restart_ollama() -> dict[str, object]:
    """Restart the local Windows Ollama server with EmberWriter's tuned environment."""
    if platform.system() != "Windows":
        raise HTTPException(
            status_code=400,
            detail="Automatic Ollama restart is currently supported by EmberWriter on Windows only",
        )
    executable = shutil.which("ollama")
    if not executable:
        raise HTTPException(status_code=404, detail="Ollama executable was not found")

    os.environ["OLLAMA_FLASH_ATTENTION"] = "1"
    os.environ["OLLAMA_KV_CACHE_TYPE"] = "q8_0"
    os.environ["OLLAMA_NUM_PARALLEL"] = "1"
    env = os.environ.copy()
    try:
        stop_process = await asyncio.create_subprocess_exec(
            "taskkill.exe",
            "/IM",
            "ollama.exe",
            "/T",
            "/F",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await stop_process.communicate()
        await asyncio.sleep(1.0)
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        await asyncio.create_subprocess_exec(
            executable,
            "serve",
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            stdin=asyncio.subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not restart Ollama: {exc}") from exc

    await asyncio.sleep(1.5)
    return {
        "ok": True,
        "flash_attention": "1",
        "kv_cache_type": "q8_0",
        "num_parallel": "1",
    }
