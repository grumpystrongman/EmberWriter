from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .generation import generate
from .models import CraftControls, CraftProfile, ProviderConfig, VoiceProfile
from .storage import project_root, read_text, save_text

CRAFT_PROFILE_PATH = "style/craft-profile.json"
VOICE_PROFILE_PATH = "style/voice-profile.json"

VOICE_ANALYSIS_SYSTEM_PROMPT = """You are EmberWriter's Voice Lab.
Analyze the supplied fiction sample for reusable prose technique, not plot/content.
Return ONLY valid JSON matching the requested schema.

Identify what makes the writing recognizably itself: sentence rhythm, diction, imagery, dialogue habits, interiority, POV distance, sensual/romantic voice when present, signature traits, and habits the author would likely want to avoid or control.

Do not quote long passages from the sample. Do not flatten distinctive style into generic advice. Describe techniques concretely enough that another model can imitate the writing without copying sentences.
"""

QUALITY_PASS_SYSTEM_PROMPT = """You are EmberWriter's line editor for fiction.
Return ONLY the revised manuscript prose with no commentary, headings, or explanation.

Preserve the scene's events, POV, tense, character identities, relationship meaning, adult consent state, and requested heat/intensity. Do not make an explicit adult scene tamer merely because you are editing it. Do not intensify beyond the author's requested level either.

Improve the prose rather than rewriting for rewriting's sake:
- preserve distinctive voice and intentional roughness;
- remove generic AI phrasing, filler, over-explanation, repeated emotional labels, and redundant beats;
- vary sentence cadence where repetition is accidental;
- favor precise verbs and concrete sensory detail over stacked adjectives;
- keep dialogue specific to the established character rather than interchangeable banter;
- keep physical action spatially understandable without turning intimacy into mechanical choreography;
- make escalation arise from attention, anticipation, choice, vulnerability, power shifts, dialogue, and embodied reaction;
- let the scene change the relationship or emotional state when the draft intends that;
- avoid purple euphemism unless the supplied voice profile calls for it;
- avoid clinical/anatomical detachment unless the supplied voice profile calls for it;
- keep metaphors coherent with the book's existing imagery and lore.

Aim to keep roughly the same length unless tightening clearly improves the passage.
"""

HEAT_GUIDANCE = {
    "simmer": (
        "Keep physical intimacy mostly in anticipation and subtext. Build charge through proximity, attention, "
        "interrupted choices, dialogue, restraint, and specific sensory cues. Do not rush the payoff."
    ),
    "hot": (
        "Make desire unmistakable and sustained. Use concrete sensual detail, character-specific dialogue, "
        "and escalating choices while keeping emotion, POV, and relationship stakes in the foreground."
    ),
    "scorching": (
        "For consenting adult participants, the author permits explicit sexual prose and direct language. "
        "Do not fade to black or retreat into coy summary. Keep the writing embodied, character-specific, "
        "emotionally consequential, spatially clear, and consistent with the book's voice."
    ),
    "inferno": (
        "For consenting adult participants, the author wants maximum on-page explicitness supported by the "
        "configured model. Be direct rather than coy, but never let intensity replace craft: preserve voice, "
        "character psychology, pacing, mutual agency, sensory specificity, and meaningful aftermath."
    ),
}

CURVE_GUIDANCE = {
    "slow_burn": "Escalate in small irreversible steps. Delay the largest release until tension has had time to compound.",
    "steady_rise": "Increase pressure consistently, with each beat more intimate or revealing than the last.",
    "pressure_cooker": "Hold characters close under sustained restraint; use near-releases and reversals before the break.",
    "flashpoint": "Start with existing charge and ignite quickly, then spend the scene exploring consequence rather than only acceleration.",
}


def _read_json(slug: str, path: str) -> dict[str, Any] | None:
    try:
        raw = read_text(slug, path)
    except (FileNotFoundError, OSError, ValueError):
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def get_craft_profile(slug: str) -> CraftProfile:
    payload = _read_json(slug, CRAFT_PROFILE_PATH)
    if payload is None:
        return CraftProfile()
    return CraftProfile.model_validate(payload)


def save_craft_profile(slug: str, profile: CraftProfile) -> CraftProfile:
    save_text(slug, CRAFT_PROFILE_PATH, json.dumps(profile.model_dump(), indent=2, ensure_ascii=False))
    return profile


def get_voice_profile(slug: str) -> VoiceProfile | None:
    payload = _read_json(slug, VOICE_PROFILE_PATH)
    if payload is None:
        return None
    try:
        return VoiceProfile.model_validate(payload)
    except ValueError:
        return None


def save_voice_profile(slug: str, profile: VoiceProfile) -> VoiceProfile:
    save_text(slug, VOICE_PROFILE_PATH, json.dumps(profile.model_dump(), indent=2, ensure_ascii=False))
    return profile


def _voice_directive(voice: VoiceProfile) -> str:
    sections = [
        f"Voice profile: {voice.name}",
        f"Core directive: {voice.prose_directive}",
        f"Sentence rhythm: {voice.sentence_rhythm}",
        f"Diction: {voice.diction}",
        f"Imagery: {voice.imagery}",
        f"Dialogue: {voice.dialogue}",
        f"Interiority: {voice.interiority}",
        f"POV distance: {voice.pov_distance}",
        f"Sensual/romantic voice: {voice.sensual_voice}",
    ]
    if voice.signature_traits:
        sections.append("Signature traits: " + "; ".join(voice.signature_traits))
    if voice.avoidances:
        sections.append("Avoid: " + "; ".join(voice.avoidances))
    return "\n".join(sections)


def build_craft_context(slug: str, controls: CraftControls) -> tuple[str, list[str]]:
    profile = get_craft_profile(slug)
    voice = get_voice_profile(slug)
    heat = controls.heat_level or profile.default_heat
    curve = controls.tension_curve or profile.default_tension_curve

    lines = [
        "## Prose craft direction",
        "The goal is excellent fiction first. Intensity is a dramatic instrument, not the substitute for voice or character.",
        HEAT_GUIDANCE[heat],
        CURVE_GUIDANCE[curve],
        f"Sensory intensity: {controls.sensory_intensity}/5. Use multiple senses selectively; do not inventory them.",
        f"Dialogue presence: {controls.dialogue_intensity}/5. Dialogue should reveal desire, resistance, trust, humor, fear, or power rather than narrate the obvious.",
        f"Interiority: {controls.interiority}/5. Keep internal reaction specific to the POV character and avoid repetitive emotion labels.",
        "During intimate scenes, maintain participant-specific behavior. Do not make every character flirt, surrender, tease, speak, or react the same way.",
        "Build escalation through meaningful micro-shifts: permission, proximity, attention, withheld action, verbal risk, vulnerability, reciprocal choice, changed power, and consequence.",
        "Use the book's lore and recurring imagery when they genuinely belong in the moment; do not paste lore into the scene as exposition.",
        "After a major intimate turn, preserve the changed emotional/relationship state instead of snapping characters back to baseline.",
    ]
    files: list[str] = []

    if profile.prose_directive.strip():
        lines.extend(["", "Project craft profile:", profile.prose_directive.strip()])
        files.append(CRAFT_PROFILE_PATH)
    if profile.avoidances:
        lines.append("Project avoidances: " + "; ".join(profile.avoidances))
    if controls.voice_lock and voice is not None:
        lines.extend(["", "## Voice lock", _voice_directive(voice)])
        files.append(VOICE_PROFILE_PATH)
    elif controls.voice_lock:
        lines.append("Voice lock is enabled, but no analyzed voice profile exists. Follow style/author-profile.md and manuscript cadence closely.")

    return "\n".join(lines), files


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```")
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Voice Lab did not return a JSON object")
    payload = json.loads(cleaned[start : end + 1])
    if not isinstance(payload, dict):
        raise TypeError("Voice Lab returned an invalid payload")
    return payload


async def analyze_voice(
    slug: str,
    sample_text: str,
    provider: ProviderConfig,
    profile_name: str,
) -> VoiceProfile:
    user_message = f"""PROFILE NAME: {profile_name}

Return this JSON shape:
{{
  "name": "profile name",
  "prose_directive": "compact imitation directive",
  "sentence_rhythm": "cadence and syntax tendencies",
  "diction": "word choice/register",
  "imagery": "metaphor and image habits",
  "dialogue": "dialogue/banter habits",
  "interiority": "how interior thought/emotion is rendered",
  "pov_distance": "narrative distance and filtering",
  "sensual_voice": "how attraction, tension, bodies, and intimacy are rendered when present",
  "signature_traits": ["reusable trait"],
  "avoidances": ["habit or generic tendency to avoid"]
}}

STYLE SAMPLE
{sample_text[:50000]}
"""
    raw = await generate(
        provider,
        [
            {"role": "system", "content": VOICE_ANALYSIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.25,
        top_p=0.9,
        json_mode=True,
    )
    profile = VoiceProfile.model_validate(_parse_json_object(raw))
    save_voice_profile(slug, profile)
    return profile


async def quality_pass(
    provider: ProviderConfig,
    draft: str,
    author_prompt: str,
    craft_context: str,
) -> str:
    if not draft.strip():
        return draft
    user_message = f"""AUTHOR INTENT
{author_prompt}

CRAFT / VOICE CONSTRAINTS
{craft_context}

DRAFT TO LINE-EDIT
{draft}
"""
    return await generate(
        provider,
        [
            {"role": "system", "content": QUALITY_PASS_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.35,
        top_p=0.9,
    )


def craft_files(slug: str) -> list[str]:
    root = project_root(slug)
    return [
        path
        for path in (CRAFT_PROFILE_PATH, VOICE_PROFILE_PATH)
        if (root / Path(path)).exists()
    ]
