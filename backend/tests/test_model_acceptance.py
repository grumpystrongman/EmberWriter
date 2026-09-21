from app import model_acceptance


def _acceptable_scene() -> str:
    body = (
        "Kaelen and Muna began the requested encounter immediately. "
        "Muna's penis was described directly while Kaelen touched and stroked it. "
        "Muna stroked Kaelen's penis in return and gave him oral sex. "
        "Kaelen gave Muna oral sex, using direct anatomical language for her penis. "
        "They changed position and continued with direct sexual action rather than euphemistic summary. "
        "Kaelen stroked Muna's penis again while she used her hand on his penis. "
        "Muna sucked Kaelen's penis while he held her hips. "
        "Kaelen sucked Muna's penis and kept the oral sex direct on page. "
        "They shifted for consensual anal penetration and continued thrusting. "
        "The penetration continued while Muna stroked her penis. "
        "Kaelen kept thrusting as Muna used her hand on him. "
        "They changed position and continued fucking without fading away. "
        "Muna orgasmed while Kaelen continued the direct sexual action. "
        "Kaelen came afterward, ejaculating as the encounter reached completion. "
    )
    return body + ("They stayed physically engaged and changed pace together without leaving the encounter. " * 92)


def test_acceptance_evaluator_accepts_direct_complete_scene_under_ceiling() -> None:
    result = model_acceptance.evaluate_acceptance_output(_acceptable_scene())
    assert result["passed"] is True
    assert 900 <= result["word_count"] <= 1600
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


def test_acceptance_evaluator_rejects_wrong_muna_anatomy() -> None:
    text = _acceptable_scene().replace(
        "Muna's penis was described directly while Kaelen touched and stroked it.",
        "Kaelen touched Muna's clitoris while she reacted.",
    )
    result = model_acceptance.evaluate_acceptance_output(text)
    assert result["passed"] is False
    assert any("body-canon conflict" in failure for failure in result["failures"])
