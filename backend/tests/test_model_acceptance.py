from app import model_acceptance


def _acceptable_scene() -> str:
    body = (
        "Kaelen and Muna stayed together after the sauna. "
        "They were consenting adults and spoke plainly about what they wanted. "
        "Kaelen touched Muna's pussy and clitoris while she stroked his cock. "
        "She sucked his cock during oral sex while he touched her vulva. "
        "He penetrated her vagina and thrust while they stayed focused on each other. "
        "Muna stroked his penis again as he continued penetration. "
        "They kept fucking with direct thrusting instead of euphemistic summary. "
        "Muna orgasmed first; Kaelen came afterward, ejaculating as the encounter reached its ending. "
        "They remained together afterward, talking quietly and checking in with each other. "
    )
    return body + ("They laughed, kissed, and stayed present with each other. " * 70)


def test_acceptance_evaluator_accepts_direct_complete_scene_under_ceiling() -> None:
    result = model_acceptance.evaluate_acceptance_output(_acceptable_scene())
    assert result["passed"] is True
    assert 500 <= result["word_count"] < 1300
    assert result["failures"] == []


def test_acceptance_evaluator_rejects_euphemistic_scene() -> None:
    text = (
        "Kaelen and Muna left the sauna together. They kissed and felt their souls connect. "
        + ("Their connection deepened in warmth and trust. " * 90)
    )
    result = model_acceptance.evaluate_acceptance_output(text)
    assert result["passed"] is False
    assert any("explicit" in failure or "anatom" in failure for failure in result["failures"])


def test_acceptance_evaluator_rejects_word_ceiling_violation() -> None:
    text = _acceptable_scene() + ("Kaelen and Muna stayed close. " * 350)
    result = model_acceptance.evaluate_acceptance_output(text)
    assert result["passed"] is False
    assert any("word ceiling" in failure for failure in result["failures"])


def test_acceptance_evaluator_rejects_unrelated_character_drift() -> None:
    text = _acceptable_scene() + " Sera entered the room."
    result = model_acceptance.evaluate_acceptance_output(text)
    assert result["passed"] is False
    assert any("character drift" in failure for failure in result["failures"])
