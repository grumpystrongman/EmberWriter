from app import generation_reliability_refinement as reliability


def test_vague_euphemistic_scene_cannot_pass_explicit_delivery_gate() -> None:
    prompt = (
        "Write an explicit detailed sex scene with penetration and genitalia between consenting adults; "
        "both will have an orgasm."
    )
    vague = (
        "They undressed and touched, their bodies merging in shared ecstasy until they reached a climax. "
        "Afterward they held each other and talked about what the moment meant."
    )

    failure = reliability.explicit_delivery_failure(prompt, vague)
    assert "lacks enough direct" in failure


def test_direct_scene_evidence_can_satisfy_explicit_delivery_gate() -> None:
    prompt = (
        "Write an explicit detailed sex scene with penetration between consenting adults; "
        "both will have an orgasm."
    )
    direct = (
        "He stroked his cock before penetration, then thrust while they stayed connected and responsive. "
        "She orgasmed first; he came afterward. They slowed down and checked in with each other."
    )

    assert reliability.direct_explicitness_score(direct) >= 3
    assert reliability.explicit_delivery_failure(prompt, direct) == ""


def test_generic_adult_intimacy_prompt_keeps_existing_verifier_behavior() -> None:
    prompt = "Write a complete adult intimacy scene between two consenting adults."
    assert reliability.requires_direct_explicitness(prompt) is False
