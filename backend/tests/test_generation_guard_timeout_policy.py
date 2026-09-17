from app import generation_guard, local_model_stream_reliability


def test_default_total_deadline_is_only_an_emergency_ceiling(monkeypatch) -> None:
    monkeypatch.delenv("EMBER_GENERATION_TIMEOUT_SECONDS", raising=False)

    total = generation_guard.generation_timeout_seconds()

    assert total == 6 * 60 * 60
    assert total > 10 * local_model_stream_reliability._FIRST_TOKEN_TIMEOUT_SECONDS


def test_total_deadline_can_still_be_overridden(monkeypatch) -> None:
    monkeypatch.setenv("EMBER_GENERATION_TIMEOUT_SECONDS", "1234")

    assert generation_guard.generation_timeout_seconds() == 1234.0


def test_invalid_timeout_override_falls_back_to_safe_default(monkeypatch) -> None:
    monkeypatch.setenv("EMBER_GENERATION_TIMEOUT_SECONDS", "not-a-number")

    assert generation_guard.generation_timeout_seconds() == 6 * 60 * 60
