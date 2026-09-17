from app import performance_telemetry as telemetry


def setup_function() -> None:
    telemetry.reset_for_tests()


def test_model_call_calculates_prompt_and_generation_rates() -> None:
    call = telemetry.record_model_call(
        stage="studio-prose",
        model="test:8b",
        context_tokens=8192,
        performance_profile="fast",
        payload={
            "prompt_eval_count": 1000,
            "prompt_eval_duration": 2_000_000_000,
            "eval_count": 200,
            "eval_duration": 10_000_000_000,
            "load_duration": 500_000_000,
        },
        first_token_ms=2500,
        total_ms=12500,
    )

    assert call["prompt_tokens_per_second"] == 500.0
    assert call["tokens_per_second"] == 20.0
    assert call["prompt_eval_ms"] == 2000.0
    assert call["eval_ms"] == 10000.0
    assert call["load_ms"] == 500.0
    assert call["first_token_ms"] == 2500.0


def test_snapshot_keeps_recent_model_calls() -> None:
    telemetry.record_model_call(
        stage="studio-verifier",
        model="test:12b",
        context_tokens=8192,
        performance_profile="quality",
        payload={"eval_count": 22, "eval_duration": 1_000_000_000},
        total_ms=1200,
    )

    result = telemetry.snapshot()

    calls = result["recent_calls"]
    assert isinstance(calls, list)
    assert calls[-1]["stage"] == "studio-verifier"
    assert calls[-1]["tokens_per_second"] == 22.0
