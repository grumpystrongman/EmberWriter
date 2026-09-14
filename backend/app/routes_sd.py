from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/stable-diffusion", tags=["stable-diffusion"])

DEFAULT_SD_URL = "http://127.0.0.1:7860"
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "host.docker.internal"}
_COMMON_PORTS = (7860, 7861)


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
    async with httpx.AsyncClient(timeout=timeout) as client:
        for url in urls:
            result = await probe_sd_url(client, url)
            attempts.append(result)
            if result["ok"]:
                resolved = str(result["url"])
                return {
                    "ok": True,
                    "configured_url": configured,
                    "resolved_url": resolved,
                    "auto_detected": resolved != configured,
                    "server_type": result["kind"],
                    "model": result.get("model", ""),
                    "message": (
                        f"Stable Diffusion is ready at {resolved}."
                        if resolved == configured
                        else f"Stable Diffusion was not available at {configured}, but EmberWriter found it at {resolved}."
                    ),
                    "attempts": attempts,
                    "suggestions": [],
                }

    kinds = {str(item.get("kind")) for item in attempts}
    if "comfyui" in kinds:
        message = "ComfyUI is running, but this EmberWriter image integration expects an AUTOMATIC1111/Forge-compatible WebUI API."
    elif "api_missing" in kinds:
        message = "A local web service is running, but its /sdapi/v1 API is unavailable."
    elif "authentication" in kinds:
        message = "The configured image server is reachable but requires authentication."
    elif "timeout" in kinds:
        message = "EmberWriter found a slow or stalled image-service address, but no usable WebUI API."
    else:
        message = "No compatible Stable Diffusion WebUI API was reachable on the configured or common local addresses."

    return {
        "ok": False,
        "configured_url": configured,
        "resolved_url": None,
        "auto_detected": False,
        "server_type": None,
        "model": "",
        "message": message,
        "attempts": attempts,
        "suggestions": [
            "Start AUTOMATIC1111 or Forge and enable its API (normally --api).",
            "The usual local address is http://127.0.0.1:7860; Forge/A1111 may use another port if 7860 is busy.",
            "If EmberWriter runs in Docker or WSL while Stable Diffusion runs on Windows, expose the WebUI with --listen and use the host address (often host.docker.internal from Docker).",
            "Open the WebUI's /docs page to confirm that /sdapi/v1/txt2img exists.",
        ],
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
            "message": str(exc),
            "attempts": [],
            "suggestions": ["Enter a server such as http://127.0.0.1:7860."],
        }
