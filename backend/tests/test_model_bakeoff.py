from app import model_bakeoff


def _report(model: str, *, passed: bool, passes: int, failures: int, words: int) -> dict[str, object]:
    return {
        "requested_model": model,
        "passed": passed,
        "passes": passes,
        "results": [
            {
                "word_count": words,
                "failures": [f"failure-{index}" for index in range(failures)],
            }
        ],
    }


def test_bakeoff_only_selects_a_model_that_passed_acceptance() -> None:
    failing = _report(model_bakeoff.PYGMALION_3_12B, passed=False, passes=2, failures=1, words=900)
    passing = _report(model_bakeoff.MAGNUM_V4_12B, passed=True, passes=3, failures=0, words=850)
    assert model_bakeoff.choose_adult_model([failing, passing]) == model_bakeoff.MAGNUM_V4_12B


def test_bakeoff_prefers_more_consistent_passing_candidate() -> None:
    pyg = _report(model_bakeoff.PYGMALION_3_12B, passed=True, passes=3, failures=0, words=800)
    magnum = _report(model_bakeoff.MAGNUM_V4_12B, passed=True, passes=2, failures=0, words=1000)
    assert model_bakeoff.choose_adult_model([magnum, pyg]) == model_bakeoff.PYGMALION_3_12B


def test_bakeoff_has_no_winner_when_both_fail() -> None:
    pyg = _report(model_bakeoff.PYGMALION_3_12B, passed=False, passes=1, failures=2, words=700)
    magnum = _report(model_bakeoff.MAGNUM_V4_12B, passed=False, passes=2, failures=1, words=900)
    assert model_bakeoff.choose_adult_model([pyg, magnum]) == ""
