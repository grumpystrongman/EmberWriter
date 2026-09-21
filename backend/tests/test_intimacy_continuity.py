from app import intimacy_continuity


def test_body_state_contract_separates_anatomy_gender_and_role() -> None:
    contract = intimacy_continuity.BODY_STATE_CONTRACT
    assert "anatomy as immutable character metadata" in contract
    assert "sexual role as dynamic scene state" in contract
    assert "SOURCE_OWNER.SOURCE -> RECEIVER.RECEIVING_LOCATION" in contract
    assert "A penis is not an open cavity" in contract
    assert "Do not teleport hands, mouths, heads, hips, legs, genitals, or entire bodies" in contract


def test_body_state_contract_requires_freeze_frame_and_reachability() -> None:
    contract = intimacy_continuity.BODY_STATE_CONTRACT
    assert "CONTINUITY FREEZE-FRAME" in contract
    assert "REACHABILITY CHECK" in contract
    assert "SCENE INTENT IS DISTINCT FROM CURRENT ACTION" in contract


def test_body_state_ledger_tracks_dynamic_physical_state() -> None:
    ledger = intimacy_continuity.BODY_STATE_LEDGER_INSTRUCTION
    assert "SILENT PHYSICAL STATE LEDGER" in ledger
    assert "penetration_source" in ledger
    assert "penetration_target" in ledger
    assert "required_transition" in ledger
    assert "Do NOT print this ledger" in ledger
    assert "physical possibility wins" in ledger


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


def test_rejects_head_entering_anal_opening() -> None:
    draft = (
        "Avery knelt behind Rowan. "
        "He somehow pushed his head inside Rowan's anal sphincter."
    )
    reason = intimacy_continuity.hard_choreography_failure(draft)
    assert "head or face" in reason


def test_rejects_anal_opening_enclosing_head() -> None:
    draft = (
        "Avery lowered his face toward Rowan. "
        "Rowan's anal sphincter tightened around Avery's head."
    )
    reason = intimacy_continuity.hard_choreography_failure(draft)
    assert "head or face" in reason


def test_rejects_impossible_tongue_depth() -> None:
    draft = (
        "Avery used his tongue against Rowan's anus. "
        "His tongue pushed into the depths of Rowan's anal canal."
    )
    reason = intimacy_continuity.hard_choreography_failure(draft)
    assert "tongue" in reason
    assert "capability" in reason


def test_allows_external_tongue_contact_without_capability_inflation() -> None:
    draft = (
        "Avery moved behind Rowan and lowered his mouth. "
        "His tongue traced the outside of Rowan's anus before briefly pressing against the opening."
    )
    assert intimacy_continuity.hard_choreography_failure(draft) == ""


def test_verifier_requires_physical_continuity() -> None:
    instruction = intimacy_continuity.VERIFIER_CONTINUITY_INSTRUCTION
    assert "physical_continuity is true only when" in instruction
    assert "SOURCE_OWNER.SOURCE -> RECEIVER.RECEIVING_LOCATION" in instruction
    assert "normal anatomical capability" in instruction
    assert "facing direction" in instruction
    assert "relative location" in instruction
