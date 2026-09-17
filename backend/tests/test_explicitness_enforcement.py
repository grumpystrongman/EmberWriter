from app import generation
from app.explicitness_enforcement import explicitness_profile, strict_explicit_delivery_failure


_PROMPT = (
    "Write an explicit sex scene between consenting adults with penetration, genitalia, oral sex, "
    "and both having an orgasm. Keep it under 1300 words."
)


def test_pg13_euphemistic_scene_fails_direct_explicitness_gate() -> None:
    draft = (
        "They undressed and moved together on the bench. Skin met skin as the room filled with steam. "
        "With a final push he breached her fully and they found a steady rhythm. Their bodies moved "
        "together until they reached culmination and climax. They collapsed together afterward, satisfied."
    )
    reason = strict_explicit_delivery_failure(_PROMPT, draft)
    assert reason
    assert "anatom" in reason.lower() or "pg-13" in reason.lower() or "euphem" in reason.lower()


def test_direct_lexical_fixture_passes_density_gate() -> None:
    draft = (
        "Kaelen's penis pressed against Muna's vagina before penetration began. "
        "He thrust his penis into her vagina while she touched her clitoris. "
        "Muna stroked his penis with her hand and then gave him oral sex. "
        "He licked her vulva and clitoris while she guided him with her hand. "
        "They continued fucking, with direct penetration and thrusting described clearly. "
        "Muna orgasmed first. Kaelen came afterward, ejaculating as they finished together."
    )
    profile = explicitness_profile(draft)
    assert profile.anatomy_groups >= 2
    assert profile.action_groups >= 2
    assert profile.direct_action_sentences >= 3
    assert profile.explicit_sentences >= 5
    assert strict_explicit_delivery_failure(_PROMPT, draft) == ""


def test_explicit_request_adds_direct_vocabulary_contract() -> None:
    messages = generation.build_messages(
        "write",
        "Write an explicit scene with penetration, blowjobs, hand jobs, cumming, and orgasms under 1300 words.",
        "Both participants are consenting adults. Relevant intimate anatomy is established in canon.",
        heat_level="inferno",
        min_scene_words=700,
    )
    system = messages[0]["content"]
    assert "Direct-explicitness contract" in system
    assert "penetration" in system
    assert "blowjobs" in system
    assert "cumming" in system
    assert "Do not downgrade it to romance-only, PG-13" in system
