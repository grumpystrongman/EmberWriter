from pathlib import Path

from app import character_voice, prose_quality, storage
from app.character_voice import CharacterVoiceCard, CharacterVoiceState


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_character_voice_round_trip_and_context(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Voice Cards")
    slug = project["slug"]

    saved = character_voice.save_character_voices(
        slug,
        CharacterVoiceState(
            voices=[
                CharacterVoiceCard(
                    character="Mara",
                    speech_rhythm="Short answers when threatened; longer sentences when she is explaining a plan.",
                    vocabulary="Concrete and practical.",
                    humor="Dry deflection.",
                    emotional_expression="Acts before naming emotion.",
                    subtext="Uses questions to test trust.",
                    physical_mannerisms="Stillness under pressure.",
                    intimacy_expression="Affection appears first as attention and protective detail.",
                    signature_phrases=["You sure?"],
                    avoidances=["flowery reassurance"],
                    author_notes="Never make her gush.",
                )
            ]
        ),
    )

    assert saved.voices[0].character == "Mara"
    loaded = character_voice.load_character_voices(slug)
    assert loaded.voices[0].humor == "Dry deflection."

    context, files = character_voice.build_character_voice_context(slug, ["Mara"])
    assert "Short answers when threatened" in context
    assert "Never make her gush" in context
    assert character_voice.VOICE_PATH in files


def test_character_voice_upsert_replaces_matching_character(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Voice Upsert")
    slug = project["slug"]

    character_voice.upsert_character_voice(slug, CharacterVoiceCard(character="Mara", humor="Dry."))
    state = character_voice.upsert_character_voice(slug, CharacterVoiceCard(character="mara", humor="Sharper."))

    assert len(state.voices) == 1
    assert state.voices[0].humor == "Sharper."


def test_prose_quality_finds_generic_patterns_and_repetition() -> None:
    text = (
        "For a moment, he said nothing. For a moment, she waited. For a moment, the room went still. "
        "The tension between them hung in the air. Her heart kicked. Her heart slowed. Her heart kicked again. "
        "Her heart seemed too loud. Her heart would not settle. Her heart betrayed her. "
        "She was nervous. She was nervous. She was nervous."
    )
    issues = prose_quality.diagnose_prose(text)

    assert any("Generic/AI-associated phrasing" in issue for issue in issues)
    assert any("Emotion is repeatedly named" in issue for issue in issues)
    assert any("Physical reaction vocabulary is clustering" in issue for issue in issues)


def test_prose_quality_keeps_clean_text_low_noise() -> None:
    text = (
        "Mara checked the deadbolt twice, then left the key in the lock.\n\n"
        '"You staying?"\n\n'
        "Cal looked at the wet footprints crossing the kitchen tile. He took his time answering. "
        '"Until we know who made those."'
    )
    assert len(prose_quality.diagnose_prose(text)) <= 1
