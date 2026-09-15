from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .model_preferences import preferred_local_model

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LOG_DIR = _REPO_ROOT / ".ember" / "logs"
_START_LOCK = asyncio.Lock()
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_RECOMMENDED_MODELS = (
    "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m",
    "R4C3R/qwen3-8b-heretic:q4_k_m",
)


def _normalized_base_url(base_url: str) -> str:
    value = (base_url or "http://127.0.0.1:11434").strip().rstrip("/")
    if not value.startswith(("http://", "https://")):
        value = f"http://{value}"
    return value


def is_local_ollama_url(base_url: str) -> bool:
    try:
        parsed = urlsplit(_normalized_base_url(base_url))
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold()
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.scheme == "http" and host in _LOCAL_HOSTS and port == 11434


async def _probe(base_url: str) -> bool:
    try:
        timeout = httpx.Timeout(connect=1.5, read=2.0, write=2.0, pool=1.5)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.get(f"{_normalized_base_url(base_url)}/api/tags")
            return response.status_code < 500
    except httpx.HTTPError:
        return False


def _tail(path: Path, limit: int = 30) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-limit:]).strip()


def _start_ollama_process(base_url: str) -> subprocess.Popen[bytes]:
    executable = shutil.which("ollama")
    if not executable:
        raise RuntimeError(
            "The local writing model server is not running and Ollama is not available on PATH. "
            "EmberWriter will not discard or replace your installed models; repair the Ollama installation instead."
        )

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    stdout_path = _LOG_DIR / "ollama.out.log"
    stderr_path = _LOG_DIR / "ollama.err.log"
    stdout_handle = stdout_path.open("ab")
    stderr_handle = stderr_path.open("ab")
    env = os.environ.copy()
    parsed = urlsplit(_normalized_base_url(base_url))
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11434
    env["OLLAMA_HOST"] = f"{host}:{port}"

    kwargs: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": stdout_handle,
        "stderr": stderr_handle,
        "cwd": str(_REPO_ROOT),
        "env": env,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        kwargs["start_new_session"] = True

    try:
        process = subprocess.Popen([executable, "serve"], **kwargs)  # type: ignore[arg-type]
    finally:
        stdout_handle.close()
        stderr_handle.close()
    return process


async def ensure_ollama_ready(base_url: str, timeout_seconds: float = 20.0) -> None:
    """Start a local Ollama service when needed; never downloads or replaces models."""

    if not is_local_ollama_url(base_url):
        return
    if await _probe(base_url):
        return

    async with _START_LOCK:
        if await _probe(base_url):
            return

        process = _start_ollama_process(base_url)
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            if await _probe(base_url):
                return
            if process.poll() is not None:
                break
            await asyncio.sleep(0.5)

        stderr_tail = _tail(_LOG_DIR / "ollama.err.log")
        detail = f" Last Ollama log lines: {stderr_tail}" if stderr_tail else ""
        raise RuntimeError(
            f"Ollama did not become ready at {_normalized_base_url(base_url)} within {int(timeout_seconds)} seconds.{detail}"
        )


async def installed_ollama_models(base_url: str) -> list[str]:
    await ensure_ollama_ready(base_url)
    timeout = httpx.Timeout(connect=3.0, read=10.0, write=10.0, pool=3.0)
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        response = await client.get(f"{_normalized_base_url(base_url)}/api/tags")
        response.raise_for_status()
        payload = response.json()
    return [
        str(item.get("name", "")).strip()
        for item in payload.get("models", [])
        if str(item.get("name", "")).strip()
    ]


def choose_installed_model(configured_model: str, installed_models: list[str]) -> str:
    by_name = {item.casefold(): item for item in installed_models}
    configured = configured_model.strip()
    if configured and configured.casefold() in by_name:
        return by_name[configured.casefold()]

    preferred = preferred_local_model()
    if preferred and preferred.casefold() in by_name:
        return by_name[preferred.casefold()]

    for model in _RECOMMENDED_MODELS:
        if model.casefold() in by_name:
            return by_name[model.casefold()]

    return installed_models[0] if installed_models else ""
