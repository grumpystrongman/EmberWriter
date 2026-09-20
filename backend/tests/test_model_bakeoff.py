import asyncio
import json

from app import model_acceptance, writing_model_catalog


def test_acceptance_locks_requested_model(monkeypatch) -> None:
    seen_models: list[tuple[str, bool]] = []

    async def fake_generate(config, messages, **kwargs):
        del messages, kwargs
        seen_models.append((config.model, config.lock_model))
        return "synthetic result"

    monkeypatch.setattr(model_acceptance.generation, "generate_complete_prose", fake_generate)
    monkeypatch.setattr(
        model_acceptance,
        "evaluate_acceptance_output",
        lambda _text: {"passed": True, "word_count": 900, "failures": []},
    )

    report = asyncio.run(
        model_acceptance.run_model_acceptance(
            writing_model_catalog.PYGMALION_3_12B,
            attempts=2,
        )
    )

    assert report["passed"] is True
    assert seen_models == [
        (writing_model_catalog.PYGMALION_3_12B, True),
        (writing_model_catalog.PYGMALION_3_12B, True),
    ]


def test_bakeoff_selects_reliable_candidate_not_longest_output(monkeypatch) -> None:
    async def fake_acceptance(model, **kwargs):
        del kwargs
        if model == writing_model_catalog.MAGNUM_V4_12B:
            return {
                "requested_model": model,
                "passes": 3,
                "passed": True,
                "results": [
                    {"passed": True, "word_count": 880, "failures": []},
                    {"passed": True, "word_count": 910, "failures": []},
                    {"passed": True, "word_count": 900, "failures": []},
                ],
            }
        return {
            "requested_model": model,
            "passes": 2,
            "passed": False,
            "results": [
                {"passed": True, "word_count": 1200, "failures": []},
                {"passed": True, "word_count": 1250, "failures": []},
                {"passed": False, "word_count": 1290, "failures": ["buildup only"]},
            ],
        }

    monkeypatch.setattr(model_acceptance, "run_model_acceptance", fake_acceptance)
    report = asyncio.run(model_acceptance.run_model_bakeoff(attempts=3))

    assert report["passed"] is True
    assert report["best_model"] == writing_model_catalog.MAGNUM_V4_12B


def test_catalog_honors_persisted_bakeoff_winner(tmp_path, monkeypatch) -> None:
    report_path = tmp_path / "writing-model-bakeoff.json"
    report_path.write_text(
        json.dumps(
            {
                "passed": True,
                "best_model": writing_model_catalog.MAGNUM_V4_12B,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(writing_model_catalog, "_BAKEOFF_REPORT_PATH", report_path)

    installed = [
        writing_model_catalog.PYGMALION_3_12B,
        writing_model_catalog.MAGNUM_V4_12B,
        writing_model_catalog.HERETIC_ROCINANTE_12B,
    ]

    assert writing_model_catalog.preferred_adult_model(installed) == writing_model_catalog.MAGNUM_V4_12B


def test_catalog_falls_back_to_primary_candidate_without_bakeoff(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        writing_model_catalog,
        "_BAKEOFF_REPORT_PATH",
        tmp_path / "missing-bakeoff.json",
    )
    installed = [
        writing_model_catalog.MAGNUM_V4_12B,
        writing_model_catalog.PYGMALION_3_12B,
    ]

    assert writing_model_catalog.preferred_adult_model(installed) == writing_model_catalog.PYGMALION_3_12B
