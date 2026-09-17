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
    assert failure
    assert "anatom" in failure.lower() or "explicit" in failure.lower() or "euphem" in failure.lower()


def test_direct_scene_evidence_can_satisfy_explicit_delivery_gate() -> None:
    prompt = (
        "Write an explicit detailed sex scene with penetration between consenting adults; "
        "both will have an orgasm."
    )
    direct = (
        "He stroked his cock while she touched her vagina and clitoris. "
        "She sucked his cock during oral sex while he responded directly. "
        "He penetrated her vagina and thrust while they stayed connected and responsive. "
        "She stroked his penis again as he continued penetration. "
        "They kept fucking with direct thrusting rather than euphemistic description. "
        "She orgasmed first; he came afterward and ejaculated. "
        "They slowed down and checked in with each other."
    )

    assert reliability.direct_explicitness_score(direct) >= 3
    assert reliability.explicit_delivery_failure(prompt, direct) == ""


def test_generic_adult_intimacy_prompt_keeps_existing_verifier_behavior() -> None:
    prompt = "Write a complete adult intimacy scene between two consenting adults."
    assert reliability.requires_direct_explicitness(prompt) is False
