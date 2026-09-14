from __future__ import annotations

from typing import Any

from .character_voice import build_character_voice_context
from .craft import build_craft_context
from .generation import generate
from .models import CraftControls, ProviderConfig
from .prose_quality import quality_guidance
from .provenance_store import record_assistance_event
from .storage import compile_context
from .story_intelligence import build_character_context, relevant_character_names
from .voice_audit import analyze_voice_text

VOICE_STRENGTHEN_SYSTEM_PROMPT = """You are EmberWriter's author-voice line editor.
Return ONLY revised manuscript prose. Do not add headings, notes, explanations, or commentary.

Your job is to make the passage sound more recognizably like this project's established author voice while preserving what the author actually wrote and meant.

Preserve:
- scene events, facts, chronology, POV, tense, and character identities;
- relationship meaning, consent/choice state, emotional direction, and requested intensity;
- intentional roughness, fragments, repetition, slang, profanity, humor, directness, and other useful irregularities when they belong to the author's voice;
- character-specific dialogue, interiority, imagery, and recurring lore.

Improve only where the passage benefits:
- replace generic explanatory scaffolding with concrete perception, behavior, subtext, or character-native thought;
- reduce redundant emotional restatement after the emotion is already shown;
- break accidental symmetrical constructions and repeated rhetorical templates;
- restore natural sentence-length and paragraph variation when prose has become mechanically even;
- prefer precise verbs, specific sensory detail, and scene-specific images over generic abstraction;
- keep dialogue and reactions particular to these characters rather than interchangeable;
- remove filler, repetitive transitions, generic intensifiers, and polished-but-empty phrasing;
- preserve the author's measured style tendencies as tendencies, never quotas.

Do not optimize for, mention, predict, or attempt to fool any AI detector or classifier. The target is stronger fiction and closer fidelity to the author's learned voice.
"""


def _focus_lines(audit: dict[str, Any]) -> str:
    findings = audit.get("findings") or []
    if not findings:
        return "No deterministic craft flags were material. Make only changes that clearly improve voice fidelity."
    lines: list[str] = []
    for finding in findings:
        label = str(finding.get("label", "Voice finding"))
        suggestion = str(finding.get("suggestion", "")).strip()
        lines.append(f"- {label}: {suggestion}" if suggestion else f"- {label}")
    return "\n".join(lines)


def _context_for_passage(slug: str, source_text: str, active_file: str | None, instruction: str) -> tuple[str, list[str]]:
    context_text, context_files = compile_context(
        slug,
        prompt=instruction or "Strengthen this passage while preserving story meaning and author voice.",
        active_file=active_file,
        selected_text=source_text,
    )
    names = relevant_character_names(slug, f"{source_text}\n{context_text[-12000:]}")
    character_text = build_character_context(slug, names) if names else ""
    voice_text, voice_files = build_character_voice_context(slug, names) if names else ("", [])
    blocks = [block for block in (character_text, voice_text, context_text) if block.strip()]
    return "\n\n---\n\n".join(blocks), list(dict.fromkeys([*voice_files, *context_files]))


async def strengthen_voice(
    slug: str,
    *,
    source_text: str,
    provider: ProviderConfig,
    active_file: str | None = None,
    instruction: str = "",
) -> dict[str, Any]:
    if not source_text.strip():
        raise ValueError("Choose a passage before strengthening its voice")

    before = analyze_voice_text(slug, source_text, active_file or "Selected passage")
    story_context, context_files = _context_for_passage(slug, source_text, active_file, instruction)
    craft_context, craft_files = build_craft_context(
        slug,
        CraftControls(
            voice_lock=True,
            quality_pass=False,
            sensory_intensity=3,
            dialogue_intensity=3,
            interiority=3,
        ),
    )
    deterministic_targets = quality_guidance(source_text)
    author_instruction = instruction.strip() or (
        "Strengthen the author's voice without changing the scene's events, meaning, explicitness, or character intent."
    )
    user_message = f"""AUTHOR REQUEST
{author_instruction}

VOICE-AUDIT FOCUS
{_focus_lines(before)}

DETERMINISTIC CRAFT SIGNALS
{deterministic_targets}

VOICE / CRAFT PROFILE
{craft_context}

RELEVANT STORY CONTEXT
{story_context[-32000:] if story_context else '(No additional story context was available.)'}

PASSAGE TO LINE-EDIT
{source_text}
"""
    revised = await generate(
        provider,
        [
            {"role": "system", "content": VOICE_STRENGTHEN_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.35,
        top_p=0.9,
    )
    if not revised.strip():
        raise RuntimeError("The model returned an empty voice-strengthening revision")

    after = analyze_voice_text(slug, revised, active_file or "Candidate revision")
    all_files = list(dict.fromkeys([*craft_files, *context_files]))
    event = record_assistance_event(
        slug,
        mode="voice_strengthen",
        active_file=active_file,
        prompt=author_instruction,
        selected_text=source_text,
        output_text=revised,
        context_files=all_files,
        refined=True,
        provider=provider.provider,
        model=provider.model,
    )
    return {
        "source_text": source_text,
        "revised_text": revised,
        "before": before,
        "after": after,
        "context_files": all_files,
        "assistance_event_id": event["id"],
        "disclaimer": (
            "This revision targets craft quality and fidelity to the project's learned voice. "
            "It does not estimate or promise outcomes from AI-detection systems."
        ),
    }
