from app import model_acceptance


def _acceptable_scene() -> str:
    body = (
        "Rowan and Avery began the requested encounter immediately. "
        "Avery's penis was described directly while Rowan touched and stroked it. "
        "Avery stroked Rowan's penis in return and gave him oral sex. "
        "Rowan gave Avery oral sex, using direct anatomical language for her penis. "
        "They changed position and continued with direct sexual action rather than euphemistic summary. "
        "Rowan stroked Avery's penis again while she used her hand on his penis. "
        "Avery sucked Rowan's penis while he held her hips. "
        "Rowan sucked Avery's penis and kept the oral sex direct on page. "
        "Avery lay on her back with her legs apart while Rowan moved between her legs facing her. "
        "Rowan identified Avery's anus before consensual anal penetration in the face-to-face position. "
        "The penetration continued while Avery stroked her penis. "
        "They then changed position: Avery moved onto hands and knees facing away while Rowan knelt behind her. "
        "Rowan resumed anal penetration from behind and continued thrusting in the rear position. "
        "Avery stroked her penis while the rear anal penetration continued. "
        "Avery orgasmed while Rowan continued the direct sexual action. "
        "Rowan came afterward, ejaculating as the encounter reached completion. "
    )
    tail = " ".join(
        f"They stayed physically engaged as the pace changed through continuation beat {index}."
        for index in range(92)
    )
    return body + tail + "."


def test_acceptance_evaluator_accepts_direct_complete_scene_under_ceiling() -> None:
    result = model_acceptance.evaluate_acceptance_output(_acceptable_scene())
    assert result["passed"] is True
    assert 900 <= result["word_count"] <= 1600
    assert result["failures"] == []


def test_acceptance_evaluator_rejects_euphemistic_scene() -> None:
    text = (
        "Rowan and Avery left the sauna together. They kissed and felt their souls connect. "
        + ("Their connection deepened in warmth and trust. " * 90)
    )
    result = model_acceptance.evaluate_acceptance_output(text)
    assert result["passed"] is False
    assert any("explicit" in failure or "anatom" in failure for failure in result["failures"])


def test_acceptance_evaluator_rejects_word_ceiling_violation() -> None:
    text = _acceptable_scene() + ("Rowan and Avery stayed close. " * 350)
    result = model_acceptance.evaluate_acceptance_output(text)
    assert result["passed"] is False
    assert any("word ceiling" in failure for failure in result["failures"])


def test_acceptance_evaluator_rejects_unrelated_character_drift() -> None:
    text = _acceptable_scene() + " Mira entered the room."
    result = model_acceptance.evaluate_acceptance_output(text)
    assert result["passed"] is False
    assert any("character drift" in failure for failure in result["failures"])


def test_acceptance_evaluator_rejects_wrong_muna_anatomy() -> None:
    text = _acceptable_scene().replace(
        "Avery's penis was described directly while Rowan touched and stroked it.",
        "Rowan touched Avery's clitoris while she reacted.",
    )
    result = model_acceptance.evaluate_acceptance_output(text)
    assert result["passed"] is False
    assert any("body-canon conflict" in failure for failure in result["failures"])
