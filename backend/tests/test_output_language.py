"""The author-declared prose language must reach the model as a trailing directive."""

from app import adult_specialist, generation, studio_context


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
        messages = generation.build_messages(
            "write",
            "Write the scene.",
            "canon",
            output_language=studio_context.project_output_language("horror-short-story"),
        )
        assert "Output language:" not in messages[0]["content"]


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


def test_directive_ends_the_system_prompt_so_it_outranks_english_instructions() -> None:
    messages = generation.build_messages(
        "write",
        "Write the scene.",
        "PROJECT CONTEXT\nEnglish canon.",
        heat_level="simmer",
        output_language="es",
    )
    system = messages[0]["content"]

    assert "Output language: es." in system
    assert "Write every sentence of the prose in es." in system
    assert system.rstrip().endswith("Apply it to narration, description, and dialogue alike.")
    assert messages[1]["role"] == "user"


def test_adult_specialist_carries_the_same_language_directive() -> None:
    messages = adult_specialist.build_adult_specialist_messages(
        "write",
        "Write the scene.",
        "canon",
        heat_level="inferno",
        delivery_scope="full_scene",
        min_scene_words=900,
        output_language="es",
    )
    system = messages[0]["content"]

    assert "Output language: es." in system
    assert system.rstrip().endswith("Apply it to narration, description, and dialogue alike.")


def test_language_directive_helper_short_circuits_on_empty_values() -> None:
    for value in ("", "   ", None):
        assert generation.language_directive(value) == ""
    assert "Output language: es-AR." in generation.language_directive(" es-AR ")
