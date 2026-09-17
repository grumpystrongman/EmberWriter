from app import routes_performance


def test_split_columns_handles_ollama_ps_layout() -> None:
    line = "NAME                         ID              SIZE      PROCESSOR    CONTEXT    UNTIL"

    assert routes_performance._split_columns(line) == [
        "NAME",
        "ID",
        "SIZE",
        "PROCESSOR",
        "CONTEXT",
        "UNTIL",
    ]


def test_performance_recommendations_flag_cpu_only_model(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_FLASH_ATTENTION", "1")
    monkeypatch.setenv("OLLAMA_KV_CACHE_TYPE", "q8_0")

    recommendations = routes_performance._performance_recommendations(
        [{"name": "model", "processor": "100% CPU"}]
    )

    assert any("CPU-only" in item for item in recommendations)
    assert not any("Flash Attention" in item for item in recommendations)
    assert not any("KV cache" in item for item in recommendations)


def test_performance_status_reports_runtime_env_without_tools(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_FLASH_ATTENTION", "1")
    monkeypatch.setenv("OLLAMA_KV_CACHE_TYPE", "q8_0")
    monkeypatch.setenv("OLLAMA_NUM_PARALLEL", "1")
    monkeypatch.setattr(routes_performance, "_ollama_processes", list)
    monkeypatch.setattr(routes_performance, "_nvidia_gpus", list)

    result = routes_performance.performance_status()

    assert result["ollama"]["flash_attention"] == "1"
    assert result["ollama"]["kv_cache_type"] == "q8_0"
    assert result["ollama"]["num_parallel"] == "1"
