"""The author-declared prose language must be the LAST thing in the system prompt.

The directive is applied at message-assembly time (`_generation_messages`) rather
than inside the prompt builders, because reliability layers append word-limit and
completion contracts to the system prompt after the builder returns.
"""

from app import adult_specialist, generation, studio_context
from app.models import CraftControls, GenerateRequest, ProviderConfig
from app.routes_generation import _generation_messages


def _request(prompt: str = "Write the scene.", model: str = "qwen3.5:9b") -> GenerateRequest:
    return GenerateRequest(
        prompt=prompt,
        mode="write",
        provider=ProviderConfig(provider="ollama", base_url="http://localhost:11434", model=model),
        craft=CraftControls(heat_level="simmer"),
    )


def _project(monkeypatch, language):
    monkeypatch.setattr(
        studio_context,
        "get_project",
        lambda slug: {"content_profile": {"audience": "adult", "language": language}},
    )


def test_author_controlled_language_emits_no_directive(monkeypatch) -> None:
    for language in ("", "author_controlled", "auto", "mixed", "unspecified", None):
        _project(monkeypatch, language)
        assert studio_context.project_output_language("horror-short-story") == ""


def test_declared_language_is_returned_verbatim(monkeypatch) -> None:
    for language in ("es", "es-AR", "Spanish", "pt-BR"):
        _project(monkeypatch, language)
        assert studio_context.project_output_language("horror-short-story") == language


def test_missing_or_malformed_project_language_is_ignored(monkeypatch) -> None:
    monkeypatch.setattr(
        studio_context, "get_project", lambda slug: {"content_profile": "not-a-dict"}
    )
    assert studio_context.project_output_language("horror-short-story") == ""

    def raise_missing(slug):
        raise FileNotFoundError(slug)

    monkeypatch.setattr(studio_context, "get_project", raise_missing)
    assert studio_context.project_output_language("missing") == ""


def test_directive_is_last_even_after_reliability_wrappers(monkeypatch) -> None:
    """An author word limit makes the reliability layer append its own contract.

    That contract must not displace the language instruction, or a small model
    reads an English word-count rule as the final instruction.
    """
    payload = _request(
        "Write the scene. Length: 700-900 words.\n\nSTUDIO SCENE DELIVERY CONTRACT:\n- Deliver it."
    )
    messages, specialist = _generation_messages(
        payload,
        "PROJECT CONTEXT\nEnglish canon.",
        heat="simmer",
        delivery_scope="full_scene",
        minimum_words=700,
        output_language="es",
    )
    system = messages[0]["content"]

    assert specialist is False
    assert "Spanish (español)" in system
    assert "Author word-limit contract" in system, "wrapper should have appended its contract"
    assert system.rstrip().endswith("never translate the scene into English.")
    assert messages[1]["role"] == "user"
    assert "OUTPUT LANGUAGE" not in messages[1]["content"]


def test_no_directive_when_project_language_is_author_controlled(monkeypatch) -> None:
    _project(monkeypatch, "author_controlled")
    language = studio_context.project_output_language("horror-short-story")
    messages, _ = _generation_messages(
        _request(),
        "canon",
        heat="simmer",
        delivery_scope="full_scene",
        minimum_words=700,
        output_language=language,
    )
    assert "OUTPUT LANGUAGE" not in messages[0]["content"]


def test_adult_specialist_path_also_ends_with_the_directive() -> None:
    payload = _request(
        "Write the explicit scene between the two adults.",
        model="hf.co/mradermacher/Qwen3.5-4B-NSFW-ARA-Heretic-Literotica-i1-GGUF:Q4_K_M",
    )
    messages, specialist = _generation_messages(
        payload,
        "canon\nProject audience: adult.",
        heat="inferno",
        delivery_scope="full_scene",
        minimum_words=900,
        output_language="es",
    )
    system = messages[0]["content"]

    assert specialist is True
    assert "adult-fiction scene specialist" in system
    assert "Spanish (español)" in system
    assert system.rstrip().endswith("never translate the scene into English.")


def test_language_directive_helper_short_circuits_on_empty_values() -> None:
    for value in ("", "   ", None):
        assert generation.language_directive(value) == ""
    assert "Spanish (español)" in generation.language_directive(" es-AR ")
    assert "Spanish (español)" in generation.language_directive("es_MX")


def test_language_codes_are_named_not_left_as_bare_codes() -> None:
    """A bare "es" is weak evidence for a small model; name the language."""
    assert "Spanish (español)" in generation.language_directive("es")
    assert "Portuguese (português)" in generation.language_directive("pt-BR")
    assert "Japanese (日本語)" in generation.language_directive("ja")
    # Unknown codes still speak for themselves rather than falling back to English.
    assert "Klingon" in generation.language_directive("Klingon")


def test_builders_do_not_hardcode_a_language() -> None:
    """Language lives in one place; the builders stay language-agnostic."""
    messages = generation.build_messages("write", "Write it.", "canon", heat_level="simmer")
    assert "OUTPUT LANGUAGE" not in messages[0]["content"]

    adult = adult_specialist.build_adult_specialist_messages(
        "write", "Write it.", "canon", heat_level="inferno",
        delivery_scope="full_scene", min_scene_words=900,
    )
    assert "OUTPUT LANGUAGE" not in adult[0]["content"]
