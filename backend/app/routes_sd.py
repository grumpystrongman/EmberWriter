from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/stable-diffusion", tags=["stable-diffusion"])

DEFAULT_SD_URL = "http://127.0.0.1:7860"
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "host.docker.internal"}
_COMMON_PORTS = (7860, 7861)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_MANAGED_CONFIG = _REPO_ROOT / ".ember" / "image-engine.json"
_MANAGED_RUNTIME = _REPO_ROOT / ".ember" / "image-engine-runtime.json"
_MANAGED_LAUNCHER = _REPO_ROOT / "scripts" / "start-image-engine.ps1"
_MANAGED_LOG_DIR = _REPO_ROOT / ".ember" / "logs"
_managed_supervisor: subprocess.Popen[bytes] | None = None


def normalize_sd_url(value: str) -> str:
    raw = (value or DEFAULT_SD_URL).strip()
    if not raw:
        raw = DEFAULT_SD_URL
    if not raw.startswith(("http://", "https://")):
        raw = f"http://{raw}"
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Stable Diffusion server must be a valid http(s) address")

    path = parsed.path.rstrip("/")
    known_suffixes = (
        "/sdapi/v1/txt2img",
        "/sdapi/v1/img2img",
        "/sdapi/v1/options",
        "/sdapi/v1",
        "/docs",
    )
    for suffix in known_suffixes:
        if path.endswith(suffix):
            path = path[: -len(suffix)].rstrip("/")
            break
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def candidate_sd_urls(configured_url: str) -> list[str]:
    configured = normalize_sd_url(configured_url)
    candidates = [configured]
    parsed = urlsplit(configured)
    host = (parsed.hostname or "").casefold()
    if host not in _LOCAL_HOSTS:
        return candidates

    for candidate_host in ("127.0.0.1", "localhost", "host.docker.internal"):
        for port in _COMMON_PORTS:
            candidate = f"http://{candidate_host}:{port}"
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def managed_image_engine_config() -> dict:
    payload = _read_json(_MANAGED_CONFIG)
    if not payload.get("managed"):
        return {}
    return payload


def managed_image_engine_state() -> dict:
    return _read_json(_MANAGED_RUNTIME)


def _is_managed_local_url(configured_url: str) -> bool:
    config = managed_image_engine_config()
    if not config:
        return False
    managed_url = normalize_sd_url(str(config.get("base_url") or DEFAULT_SD_URL))
    configured = normalize_sd_url(configured_url)
    if configured == managed_url:
        return True
    host = (urlsplit(configured).hostname or "").casefold()
    return host in _LOCAL_HOSTS and configured in candidate_sd_urls(managed_url)


def ensure_managed_image_engine() -> dict:
    """Start the managed image service without blocking the EmberWriter API.

    The PowerShell launcher is idempotent: it reuses a healthy or currently-loading
    Forge process and performs one automatic runtime repair when Forge exits during
    startup. Keeping this entry point in the API means the browser can recover the
    image service even if EmberWriter itself was launched outside start.ps1.
    """

    global _managed_supervisor

    config = managed_image_engine_config()
    if not config:
        return {
            "ok": False,
            "state": "not_installed",
            "message": "The managed image engine has not been installed yet.",
        }
    if os.name != "nt":
        return {
            "ok": False,
            "state": "unsupported_host",
            "message": "The managed image engine supervisor is currently Windows-only.",
        }
    if not _MANAGED_LAUNCHER.exists():
        return {
            "ok": False,
            "state": "launcher_missing",
            "message": "The managed image-engine launcher is missing from this EmberWriter checkout.",
        }

    if _managed_supervisor is not None and _managed_supervisor.poll() is None:
        return {
            "ok": True,
            "state": "starting",
            "message": "The managed image-engine supervisor is already running.",
            "base_url": str(config.get("base_url") or DEFAULT_SD_URL),
        }

    shell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not shell:
        return {
            "ok": False,
            "state": "powershell_missing",
            "message": "PowerShell is unavailable, so EmberWriter could not start the managed image engine.",
        }

    _MANAGED_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stdout_path = _MANAGED_LOG_DIR / "image-engine-api-supervisor.out.log"
    stderr_path = _MANAGED_LOG_DIR / "image-engine-api-supervisor.err.log"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    args = [
        shell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(_MANAGED_LAUNCHER),
        "-PassThru",
        "-WaitForReady",
        "-ReadyTimeoutSeconds",
        "1200",
    ]

    try:
        with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
            _managed_supervisor = subprocess.Popen(
                args,
                cwd=str(_REPO_ROOT),
                stdout=stdout,
                stderr=stderr,
                creationflags=creationflags,
            )
    except OSError as exc:
        return {
            "ok": False,
            "state": "launch_failed",
            "message": f"The managed image-engine supervisor could not start: {exc}",
        }

    return {
        "ok": True,
        "state": "starting",
        "message": "EmberWriter started the managed image engine in the background.",
        "base_url": str(config.get("base_url") or DEFAULT_SD_URL),
    }


async def probe_sd_url(client: httpx.AsyncClient, base_url: str) -> dict:
    normalized = normalize_sd_url(base_url)
    options_url = f"{normalized}/sdapi/v1/options"
    try:
        response = await client.get(options_url)
    except httpx.ConnectError:
        return {
            "url": normalized,
            "ok": False,
            "kind": "unreachable",
            "message": "No service accepted a connection at this address.",
        }
    except httpx.TimeoutException:
        return {
            "url": normalized,
            "ok": False,
            "kind": "timeout",
            "message": "A service answered too slowly to identify itself.",
        }
    except httpx.RequestError as exc:
        return {
            "url": normalized,
            "ok": False,
            "kind": "request_error",
            "message": f"Connection failed: {exc}",
        }

    if response.status_code in {401, 403}:
        return {
            "url": normalized,
            "ok": False,
            "kind": "authentication",
            "status_code": response.status_code,
            "message": "The server is reachable, but it requires authentication.",
        }

    if response.status_code == 404:
        try:
            comfy = await client.get(f"{normalized}/system_stats")
        except httpx.HTTPError:
            comfy = None
        if comfy is not None and comfy.status_code < 400:
            return {
                "url": normalized,
                "ok": False,
                "kind": "comfyui",
                "status_code": 404,
                "message": (
                    "ComfyUI was detected. EmberWriter currently uses the AUTOMATIC1111/Forge "
                    "WebUI API (/sdapi/v1), not the ComfyUI workflow API."
                ),
            }
        return {
            "url": normalized,
            "ok": False,
            "kind": "api_missing",
            "status_code": 404,
            "message": (
                "A web server is reachable, but the Stable Diffusion WebUI API is not available. "
                "For AUTOMATIC1111/Forge, enable the API (normally with --api)."
            ),
        }

    if response.status_code >= 400:
        return {
            "url": normalized,
            "ok": False,
            "kind": "http_error",
            "status_code": response.status_code,
            "message": f"The server returned HTTP {response.status_code} while checking its API.",
        }

    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    model = str(
        payload.get("sd_model_checkpoint")
        or payload.get("sd_checkpoint_hash")
        or payload.get("sd_model_name")
        or ""
    ).strip()
    return {
        "url": normalized,
        "ok": True,
        "kind": "webui_api",
        "status_code": response.status_code,
        "model": model,
        "message": "Stable Diffusion WebUI API is ready.",
    }


async def diagnose_stable_diffusion(base_url: str, auto_detect: bool = True) -> dict:
    configured = normalize_sd_url(base_url)
    urls = candidate_sd_urls(configured) if auto_detect else [configured]
    attempts: list[dict] = []
    timeout = httpx.Timeout(connect=1.25, read=2.5, write=2.5, pool=1.25)
    # Localhost image traffic must not inherit corporate/system proxy settings.
    async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
        for url in urls:
            result = await probe_sd_url(client, url)
            attempts.append(result)
            if result["ok"]:
                resolved = str(result["url"])
                managed = _is_managed_local_url(resolved)
                return {
                    "ok": True,
                    "configured_url": configured,
                    "resolved_url": resolved,
                    "auto_detected": resolved != configured,
                    "server_type": result["kind"],
                    "model": result.get("model", ""),
                    "managed": managed,
                    "managed_state": "ready" if managed else None,
                    "message": (
                        f"Stable Diffusion is ready at {resolved}."
                        if resolved == configured
                        else f"Stable Diffusion was not available at {configured}, but EmberWriter found it at {resolved}."
                    ),
                    "attempts": attempts,
                    "suggestions": [],
                }

    managed = _is_managed_local_url(configured)
    runtime = managed_image_engine_state() if managed else {}
    runtime_state = str(runtime.get("state") or "starting") if managed else None

    kinds = {str(item.get("kind")) for item in attempts}
    if managed:
        if runtime_state == "repairing":
            message = "EmberWriter is repairing the managed image engine automatically."
        elif runtime_state == "failed":
            message = "The managed image engine failed after an automatic repair attempt; EmberWriter will retry it."
        else:
            message = "The managed image engine is starting in the background. EmberWriter will reconnect automatically when the model is ready."
        suggestions = []
    elif "comfyui" in kinds:
        message = "ComfyUI is running, but this EmberWriter image integration expects an AUTOMATIC1111/Forge-compatible WebUI API."
        suggestions = ["Use an AUTOMATIC1111/Forge-compatible WebUI API for this image provider."]
    elif "api_missing" in kinds:
        message = "A local web service is running, but its /sdapi/v1 API is unavailable."
        suggestions = ["Enable the AUTOMATIC1111/Forge WebUI API (normally with --api)."]
    elif "authentication" in kinds:
        message = "The configured image server is reachable but requires authentication."
        suggestions = ["Use an image-server endpoint that EmberWriter can access without interactive authentication."]
    elif "timeout" in kinds:
        message = "EmberWriter found a slow or stalled image-service address, but no usable WebUI API."
        suggestions = ["Check the configured external image server and try again."]
    else:
        message = "No compatible Stable Diffusion WebUI API was reachable at the configured address."
        suggestions = ["Check the configured external image-server address."]

    return {
        "ok": False,
        "configured_url": configured,
        "resolved_url": None,
        "auto_detected": False,
        "server_type": None,
        "model": "",
        "managed": managed,
        "managed_state": runtime_state,
        "message": message,
        "attempts": attempts,
        "suggestions": suggestions,
    }


@router.get("/status")
async def stable_diffusion_status(
    base_url: str = Query(default=DEFAULT_SD_URL, max_length=1000),
    auto_detect: bool = Query(default=True),
) -> dict:
    try:
        return await diagnose_stable_diffusion(base_url, auto_detect=auto_detect)
    except ValueError as exc:
        return {
            "ok": False,
            "configured_url": base_url,
            "resolved_url": None,
            "auto_detected": False,
            "server_type": None,
            "model": "",
            "managed": False,
            "managed_state": None,
            "message": str(exc),
            "attempts": [],
            "suggestions": ["Enter a server such as http://127.0.0.1:7860."],
        }


@router.post("/managed/ensure")
async def ensure_managed_stable_diffusion() -> dict:
    config = managed_image_engine_config()
    if not config:
        return ensure_managed_image_engine()

    base_url = str(config.get("base_url") or DEFAULT_SD_URL)
    status = await diagnose_stable_diffusion(base_url, auto_detect=False)
    if status.get("ok"):
        return {
            "ok": True,
            "state": "ready",
            "message": "The managed image engine is already ready.",
            "base_url": status.get("resolved_url") or base_url,
        }
    return ensure_managed_image_engine()
