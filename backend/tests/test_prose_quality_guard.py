from app.prose_quality import diagnose_prose


def test_detects_runaway_sentence_and_abstract_inflation() -> None:
    runaway = " ".join(["destiny"] * 60) + "."
    text = runaway + " Eternal souls bound forever in a sacred timeless union with an unbreakable legacy for future generations."

    issues = diagnose_prose(text)
    joined = "\n".join(issues)

    assert "Runaway syntax detected" in joined
    assert "Abstract romantic significance" in joined


def test_detects_repeated_phrase_level_looping() -> None:
    phrase = "their hearts beat together while the room seemed to disappear around them"
    text = f"{phrase}. Something happened. {phrase}."

    issues = diagnose_prose(text)

    assert any("phrase-level repetition" in issue for issue in issues)
