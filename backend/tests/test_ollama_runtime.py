from __future__ import annotations

import pytest

from app import generation, ollama_runtime
from app.models import ProviderConfig


def test_local_ollama_url_detection_is_narrow() -> None:
    assert ollama_runtime.is_local_ollama_url("http://localhost:11434")
    assert ollama_runtime.is_local_ollama_url("http://127.0.0.1:11434/")
    assert not ollama_runtime.is_local_ollama_url("http://localhost:9999")
    assert not ollama_runtime.is_local_ollama_url("https://example.com:11434")


def test_choose_installed_model_preserves_valid_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    models = [
        "R4C3R/qwen3-8b-heretic:q4_k_m",
        "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m",
    ]
    monkeypatch.setattr(
        ollama_runtime,
        "preferred_local_model",
        lambda: "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m",
    )

    assert (
        ollama_runtime.choose_installed_model("R4C3R/qwen3-8b-heretic:q4_k_m", models)
        == "R4C3R/qwen3-8b-heretic:q4_k_m"
    )
    assert (
        ollama_runtime.choose_installed_model("old-model-that-is-gone", models)
        == "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m"
    )


@pytest.mark.asyncio
async def test_ollama_generation_repairs_stale_model_and_allows_long_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_models(_base_url: str) -> list[str]:
        return ["R4C3R/qwen3-8b-heretic:q4_k_m"]

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self) -> dict:
            return {"message": {"content": "dossier complete"}}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, json: dict):
            captured["url"] = url
            captured["body"] = json
            return FakeResponse()

    monkeypatch.setattr(generation, "installed_ollama_models", fake_models)
    monkeypatch.setattr(generation.httpx, "AsyncClient", FakeClient)

    config = ProviderConfig(
        provider="ollama",
        base_url="http://localhost:11434",
        model="stale-browser-model",
    )
    result = await generation.generate(
        config,
        [{"role": "user", "content": "Build a detailed dossier"}],
    )

    assert result == "dossier complete"
    assert config.model == "R4C3R/qwen3-8b-heretic:q4_k_m"
    assert captured["url"] == "http://localhost:11434/api/chat"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "R4C3R/qwen3-8b-heretic:q4_k_m"
    assert body["keep_alive"] == "30m"
    client_kwargs = captured["client_kwargs"]
    assert isinstance(client_kwargs, dict)
    assert client_kwargs["trust_env"] is False
    timeout = client_kwargs["timeout"]
    assert timeout.read == 1800.0
