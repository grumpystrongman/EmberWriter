from __future__ import annotations

import httpx
import pytest

from app.routes_sd import candidate_sd_urls, normalize_sd_url, probe_sd_url


def test_normalize_sd_url_accepts_common_user_inputs() -> None:
    assert normalize_sd_url("127.0.0.1:7860") == "http://127.0.0.1:7860"
    assert normalize_sd_url("http://127.0.0.1:7860/docs") == "http://127.0.0.1:7860"
    assert normalize_sd_url("http://localhost:7861/sdapi/v1/txt2img") == "http://localhost:7861"


def test_local_candidates_include_windows_host_bridge() -> None:
    candidates = candidate_sd_urls("http://127.0.0.1:7860")
    assert candidates[0] == "http://127.0.0.1:7860"
    assert "http://localhost:7860" in candidates
    assert "http://host.docker.internal:7860" in candidates
    assert "http://127.0.0.1:7861" in candidates


@pytest.mark.asyncio
async def test_probe_detects_webui_api_and_model() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/sdapi/v1/options"
        return httpx.Response(200, json={"sd_model_checkpoint": "dream-model.safetensors"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await probe_sd_url(client, "http://127.0.0.1:7860")

    assert result["ok"] is True
    assert result["kind"] == "webui_api"
    assert result["model"] == "dream-model.safetensors"


@pytest.mark.asyncio
async def test_probe_detects_comfyui_instead_of_webui() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/sdapi/v1/options":
            return httpx.Response(404)
        if request.url.path == "/system_stats":
            return httpx.Response(200, json={"system": {}})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await probe_sd_url(client, "http://127.0.0.1:8188")

    assert result["ok"] is False
    assert result["kind"] == "comfyui"
    assert "ComfyUI" in result["message"]


@pytest.mark.asyncio
async def test_probe_reports_connection_refusal_cleanly() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await probe_sd_url(client, "http://127.0.0.1:7860")

    assert result["ok"] is False
    assert result["kind"] == "unreachable"
    assert "accepted a connection" in result["message"]
