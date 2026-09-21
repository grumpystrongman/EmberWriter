from app import intimacy_continuity


def test_body_state_contract_separates_anatomy_gender_and_role() -> None:
    contract = intimacy_continuity.BODY_STATE_CONTRACT
    assert "anatomy as immutable character metadata" in contract
    assert "sexual role as dynamic scene state" in contract
    assert "SOURCE -> TARGET" in contract
    assert "A penis is not an open cavity" in contract
    assert "Do not teleport hands, mouths, hips, or bodies" in contract


def test_rejects_direct_inside_penis_choreography() -> None:
    draft = (
        "Avery wrapped a hand around Rowan's penis. "
        "Avery pushed one finger inside Rowan's penis."
    )
    reason = intimacy_continuity.hard_choreography_failure(draft)
    assert "penis as an open cavity" in reason


def test_rejects_ambiguous_finger_penetration_after_penis_handling() -> None:
    draft = (
        "Avery curled her fingers around Rowan's cock and stroked him slowly. "
        "Then she pushed one finger inside him without changing position."
    )
    reason = intimacy_continuity.hard_choreography_failure(draft)
    assert "no receiving anatomical target" in reason


def test_allows_explicit_target_and_repositioning() -> None:
    draft = (
        "Avery released Rowan's penis and moved behind him as he leaned forward. "
        "After the position change, she pressed one finger into his anus."
    )
    assert intimacy_continuity.hard_choreography_failure(draft) == ""


def test_verifier_requires_physical_continuity() -> None:
    instruction = intimacy_continuity.VERIFIER_CONTINUITY_INSTRUCTION
    assert "physical_continuity is true only when" in instruction
    assert "penetrative action has an identifiable source" in instruction
