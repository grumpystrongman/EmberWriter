import pytest

import app


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
    reason = app.explicitness_enforcement.strict_explicit_delivery_failure(_PROMPT, draft)
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
    profile = app.explicitness_enforcement.explicitness_profile(draft)
    assert profile.anatomy_groups >= 2
    assert profile.action_groups >= 2
    assert profile.direct_action_sentences >= 3
    assert profile.explicit_sentences >= 5
    assert app.explicitness_enforcement.strict_explicit_delivery_failure(_PROMPT, draft) == ""


def test_single_canon_safe_anatomy_group_can_reach_semantic_verifier() -> None:
    draft = (
        "They kept the language direct about their genitalia as penetration began. "
        "The penetration continued with clear physical action rather than implication. "
        "One partner gave the other oral sex, described directly instead of fading away. "
        "A hand job followed as the encounter changed pace. "
        "One partner orgasmed, and the other orgasmed later in the same completed scene."
    )
    profile = app.explicitness_enforcement.explicitness_profile(draft)
    assert profile.anatomy_groups == 1
    assert profile.action_groups >= 2
    assert profile.explicit_sentences >= 3
    assert app.explicitness_enforcement.strict_explicit_delivery_failure(_PROMPT, draft) == ""


def test_neutral_anatomy_language_counts_without_inventing_body_canon() -> None:
    profile = app.explicitness_enforcement.explicitness_profile(
        "Their genitalia remained explicitly described while penetration continued."
    )
    assert profile.anatomy_groups == 1
    assert profile.explicit_sentences == 1


def test_explicit_request_adds_direct_vocabulary_contract() -> None:
    messages = app.generation.build_messages(
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


def test_startup_policy_uses_same_explicit_creative_model_as_installer() -> None:
    managed = app.explicitness_enforcement.PYGMALION_3_MODEL
    assert app.model_provisioning.BASELINE_CREATIVE_MODEL == managed
    assert managed in app.ollama_runtime._RECOMMENDED_MODELS
    assert app.explicitness_enforcement.MAGNUM_V4_MODEL in app.ollama_runtime._RECOMMENDED_MODELS
    assert app.ollama_runtime._RECOMMENDED_MODELS[0] == managed


@pytest.mark.asyncio
async def test_studio_streams_provisional_text_live_while_base_verifies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[str] = []

    async def fake_base(
        _config,
        _messages,
        *,
        min_words,
        on_delta,
        on_status=None,
        max_passes=6,
        max_output_tokens=6144,
    ) -> str:
        del min_words, on_status, max_passes, max_output_tokens
        await on_delta("LIVE_PROVISIONAL_PASS")
        return "VERIFIED_FINAL_SCENE"

    async def emit(text: str) -> None:
        emitted.append(text)

    monkeypatch.setattr(app.explicitness_enforcement, "_BASE_STREAMED_COMPLETE", fake_base)
    result = await app.explicitness_enforcement.generate_verified_studio_prose_streamed(
        object(),
        [{"role": "system", "content": "STUDIO SCENE DELIVERY CONTRACT:"}],
        min_words=700,
        on_delta=emit,
    )

    assert result == "VERIFIED_FINAL_SCENE"
    assert emitted == ["LIVE_PROVISIONAL_PASS"]


@pytest.mark.asyncio
async def test_studio_stream_keeps_unverified_partial_visible_when_delivery_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    emitted: list[str] = []

    async def fake_base(
        _config,
        _messages,
        *,
        min_words,
        on_delta,
        on_status=None,
        max_passes=6,
        max_output_tokens=6144,
    ) -> str:
        del min_words, on_status, max_passes, max_output_tokens
        await on_delta("REJECTED_PROVISIONAL_PASS")
        raise app.streaming_generation.SceneDeliveryIncomplete(
            "REJECTED_PROVISIONAL_PASS",
            "delivery verifier rejected the scene",
        )

    async def emit(text: str) -> None:
        emitted.append(text)

    monkeypatch.setattr(app.explicitness_enforcement, "_BASE_STREAMED_COMPLETE", fake_base)
    with pytest.raises(app.streaming_generation.SceneDeliveryIncomplete):
        await app.explicitness_enforcement.generate_verified_studio_prose_streamed(
            object(),
            [{"role": "system", "content": "STUDIO SCENE DELIVERY CONTRACT:"}],
            min_words=700,
            on_delta=emit,
        )

    assert emitted == ["REJECTED_PROVISIONAL_PASS"]

def test_consent_analysis_loop_fails_before_more_buildup_is_accepted() -> None:
    draft = (
        "They had already agreed they wanted the encounter, but he kept asking about consent and permission. "
        "She answered that she trusted him and repeated her boundaries. He worried about safety and whether she really wanted it. "
        "They discussed trust, fear, vulnerability, choice, choosing, permission, boundaries, consent, safety, and trust again. "
        "He asked whether she was afraid, whether she felt safe, and whether choosing him was truly her choice. "
        "They remained at the threshold without advancing into the requested encounter."
    )
    reason = app.explicitness_enforcement.strict_explicit_delivery_failure(_PROMPT, draft)
    assert "re-litigating consent/trust/boundaries" in reason


def test_core_only_rejects_late_explicit_action() -> None:
    prompt = _PROMPT + " CORE ONLY."
    buildup = " ".join(f"setup{index}" for index in range(220))
    draft = (
        buildup
        + " They began penetration and thrusting. "
        + "One partner gave oral sex. A hand job followed. "
        + "They continued fucking. One orgasmed and the other came."
    )
    reason = app.explicitness_enforcement.strict_explicit_delivery_failure(prompt, draft)
    assert reason.startswith("core-only delivery failure:")
    assert "begins too late" in reason


def test_core_only_requires_sustained_direct_action_not_one_explicit_paragraph() -> None:
    prompt = _PROMPT + " CORE ONLY."
    draft = (
        "Penetration began immediately. "
        "They continued thrusting together. "
        "The rest of the encounter was described in vague romantic terms without additional direct action. "
        "Both eventually reached orgasm."
    )
    reason = app.explicitness_enforcement.strict_explicit_delivery_failure(prompt, draft)
    assert reason.startswith("core-only delivery failure:")
    assert "direct-action sentences" in reason
