"""Port-scoped alternate CPU Ollama endpoint never allows novel data to leave loopback."""
from __future__ import annotations

import pytest

from app import series_suggestions as suggestions


def test_story_endpoint_defaults_to_local_gpu_server(monkeypatch):
    monkeypatch.delenv("EMBER_STORY_OLLAMA_URL", raising=False)
    assert suggestions._local_story_endpoint() == "http://127.0.0.1:11434"


def test_story_endpoint_cpu_is_loopback_only(monkeypatch):
    monkeypatch.setenv("EMBER_STORY_OLLAMA_URL", "http://127.0.0.1:11435/")
    assert suggestions._local_story_endpoint() == "http://127.0.0.1:11435"
    for unsafe in (
        "https://remote-vendor.example:11435",
        "http://127.0.0.2:11435",
        "http://localhost:11435",
        "http://127.0.0.1:11436",
        "http://127.0.0.1:11435@remote-vendor.example",
        "file:///private",
    ):
        monkeypatch.setenv("EMBER_STORY_OLLAMA_URL", unsafe)
        with pytest.raises(ValueError, match="restricted to local"):
            suggestions._local_story_endpoint()
