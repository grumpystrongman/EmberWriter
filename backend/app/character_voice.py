from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field

from .storage import project_root, read_text, save_text

VOICE_PATH = "style/character-voices.json"


class CharacterVoiceCard(BaseModel):
    character: str = Field(min_length=1, max_length=160)
    speech_rhythm: str = Field(default="", max_length=4000)
    vocabulary: str = Field(default="", max_length=4000)
    humor: str = Field(default="", max_length=3000)
    emotional_expression: str = Field(default="", max_length=4000)
    subtext: str = Field(default="", max_length=4000)
    physical_mannerisms: str = Field(default="", max_length=3000)
    intimacy_expression: str = Field(default="", max_length=4000)
    signature_phrases: list[str] = Field(default_factory=list, max_length=40)
    avoidances: list[str] = Field(default_factory=list, max_length=40)
    author_notes: str = Field(default="", max_length=8000)


class CharacterVoiceState(BaseModel):
    schema_version: int = 1
    voices: list[CharacterVoiceCard] = Field(default_factory=list)


def _require_project(slug: str) -> None:
    if not (project_root(slug) / "project.json").exists():
        raise FileNotFoundError(slug)


def load_character_voices(slug: str) -> CharacterVoiceState:
    _require_project(slug)
    try:
        raw = read_text(slug, VOICE_PATH)
    except (FileNotFoundError, OSError, ValueError):
        return CharacterVoiceState()
    try:
        return CharacterVoiceState.model_validate_json(raw)
    except ValueError:
        return CharacterVoiceState()


def save_character_voices(slug: str, state: CharacterVoiceState) -> CharacterVoiceState:
    _require_project(slug)
    normalized: dict[str, CharacterVoiceCard] = {}
    for card in state.voices:
        normalized[card.character.casefold()] = card
    saved = CharacterVoiceState(voices=sorted(normalized.values(), key=lambda item: item.character.casefold()))
    save_text(slug, VOICE_PATH, saved.model_dump_json(indent=2))
    return saved


def upsert_character_voice(slug: str, card: CharacterVoiceCard) -> CharacterVoiceState:
    state = load_character_voices(slug)
    replaced = False
    next_cards: list[CharacterVoiceCard] = []
    for existing in state.voices:
        if existing.character.casefold() == card.character.casefold():
            next_cards.append(card)
            replaced = True
        else:
            next_cards.append(existing)
    if not replaced:
        next_cards.append(card)
    return save_character_voices(slug, CharacterVoiceState(voices=next_cards))


def delete_character_voice(slug: str, character: str) -> CharacterVoiceState:
    state = load_character_voices(slug)
    target = character.casefold().strip()
    return save_character_voices(
        slug,
        CharacterVoiceState(voices=[card for card in state.voices if card.character.casefold() != target]),
    )


def build_character_voice_context(slug: str, names: list[str]) -> tuple[str, list[str]]:
    wanted = {name.casefold().strip() for name in names if name.strip()}
    if not wanted:
        return "", []
    state = load_character_voices(slug)
    selected = [card for card in state.voices if card.character.casefold() in wanted]
    if not selected:
        return "", []
    lines = ["## Character voice cards", "Use these as performance constraints, not catchphrase generators."]
    for card in selected:
        lines.append(f"### {card.character}")
        for label, value in (
            ("Speech rhythm", card.speech_rhythm),
            ("Vocabulary/register", card.vocabulary),
            ("Humor", card.humor),
            ("Emotional expression", card.emotional_expression),
            ("Subtext", card.subtext),
            ("Physical mannerisms", card.physical_mannerisms),
            ("Intimacy/romance expression", card.intimacy_expression),
        ):
            if value.strip():
                lines.append(f"{label}: {value.strip()}")
        if card.signature_phrases:
            lines.append("Signature language cues: " + "; ".join(card.signature_phrases))
        if card.avoidances:
            lines.append("Avoid for this character: " + "; ".join(card.avoidances))
        if card.author_notes.strip():
            lines.append("Author notes: " + card.author_notes.strip())
    return "\n".join(lines), [VOICE_PATH]


def parse_voice_card_json(text: str, character: str) -> CharacterVoiceCard:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Character voice analysis did not return JSON")
    try:
        payload: dict[str, Any] = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("Character voice analysis returned invalid JSON") from exc
    payload["character"] = character
    return CharacterVoiceCard.model_validate(payload)
