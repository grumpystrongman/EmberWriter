from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .generation import generate
from .memory import build_memory_context, chapter_order
from .models import (
    AftermathAnalyzeRequest,
    AftermathProposal,
    ChemistryInferRequest,
    ChemistryMilestone,
    RelationshipChemistryProfile,
)
from .storage import compile_context, project_root, read_text, save_text, utc_now
from .story_intelligence import build_character_context

CHEMISTRY_DIR = "relationships/chemistry"

CHEMISTRY_SYSTEM_PROMPT = """You are EmberWriter's Relationship Chemistry analyst.
Return ONLY valid JSON for a reusable relationship chemistry profile.

Your job is not to write a scene. Distill what makes these specific adult characters combustible, tender, awkward, playful, dangerous, restrained, intimate, or emotionally consequential together. Use manuscript canon, character dossiers, relationship history, lore, and the author's direction.

Rules:
- Preserve each participant's individual voice and psychology. Do not reduce them to generic romance or erotic archetypes.
- Separate attraction from trust, vulnerability, conflict, power, and intimacy.
- Identify what creates anticipation and what would count as a genuinely new escalation for THIS relationship.
- Use lore/magic only when it actually changes the relationship or sensory/emotional experience.
- Boundaries are author-controlled facts. Leave boundaries empty unless the supplied context explicitly states them as boundaries or the author explicitly provides them.
- Never infer permission from a past act. Consent and choice remain scene-specific.
- All erotic/intimate participants must be adults.
- Avoid generic sexual choreography. Focus on character-specific cues, verbal rhythm, emotional pressure, initiation/response patterns, signature motifs, and aftermath needs.
- Do not claim an unestablished act or milestone already happened.

Return exactly this JSON shape:
{
  "participants": ["name"],
  "dynamic_summary": "current relationship dynamic",
  "attraction_language": "how attraction/desire is expressed between these people",
  "verbal_rhythm": "their specific banter, silence, directness, teasing, formality, etc.",
  "initiation_style": "how escalation tends to begin or who risks what",
  "response_style": "how the other participant(s) typically respond",
  "power_dynamic": "negotiated/interpersonal power dynamic without generic labels",
  "trust_state": "what trust currently exists and where it is fragile",
  "vulnerability_pressure": "what emotional truth or fear makes intimacy consequential",
  "established_patterns": ["already established pattern"],
  "boundaries": ["ONLY explicit author/canon boundary"],
  "signature_elements": ["distinctive relationship-specific element"],
  "lore_resonance": ["magic/lore consequence or motif"],
  "aftermath_needs": ["what emotional or story aftermath matters for these people"],
  "next_escalations": ["meaningful next step that would actually change the relationship"],
  "avoidances": ["generic or out-of-character tendency to avoid"],
  "milestones": [],
  "author_notes": ""
}
"""

AFTERMATH_SYSTEM_PROMPT = """You are EmberWriter's Aftermath analyst.
Return ONLY valid JSON describing relationship consequences from the supplied completed scene.

Do not rewrite the scene. Determine what is now different because it happened.

Rules:
- Record only changes supported by the scene.
- Do not infer or relax boundaries. Aftermath is never allowed to edit author-controlled boundaries.
- Do not convert a one-time act into permanent blanket consent.
- Distinguish physical escalation from trust, vulnerability, power, knowledge, attachment, jealousy, fear, tenderness, magic/lore effects, and unresolved pressure.
- A milestone should describe why the event matters, not provide explicit choreography.
- Preserve participant individuality and relationship asymmetry.
- If little changed, say so rather than inventing growth.
- All erotic/intimate participants must be adults.

Return exactly this JSON shape:
{
  "summary": "what changed because of the scene",
  "participants": ["name"],
  "relationship_updates": [
    {
      "participants": ["name"],
      "dynamic_summary": "new concise relationship state",
      "trust_state": "new trust state if changed",
      "vulnerability_pressure": "new vulnerability/tension state if changed",
      "add_established_patterns": ["newly established pattern only"],
      "add_signature_elements": ["new relationship-specific motif only"],
      "add_lore_resonance": ["new magic/lore relationship consequence only"],
      "add_aftermath_needs": ["aftermath that now matters"],
      "next_escalations": ["future escalation that is now meaningful"],
      "milestone_label": "short milestone name or empty",
      "milestone_consequence": "why that milestone changes the relationship"
    }
  ],
  "character_aftermath": ["individual emotional/physical/story consequence"],
  "open_questions": ["unresolved tension or boundary conversation still needed"]
}
"""


def _slug_piece(value: str) -> str:
    piece = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return piece[:60] or "character"


def normalize_participants(participants: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in participants:
        name = raw.strip()
        if not name or name.casefold() in seen:
            continue
        cleaned.append(name)
        seen.add(name.casefold())
    if not 2 <= len(cleaned) <= 6:
        raise ValueError("Relationship chemistry requires 2 to 6 unique participants")
    return cleaned


def chemistry_path(participants: list[str]) -> str:
    cleaned = normalize_participants(participants)
    key = "--".join(sorted((_slug_piece(name) for name in cleaned)))
    return f"{CHEMISTRY_DIR}/{key}.json"


def _parse_json_object(text: str, label: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.removesuffix("```").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"{label} did not return a JSON object")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise TypeError(f"{label} returned an invalid payload")
    return payload


def _load_profile_path(slug: str, path: str) -> RelationshipChemistryProfile | None:
    try:
        payload = json.loads(read_text(slug, path))
        return RelationshipChemistryProfile.model_validate(payload)
    except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def list_chemistry_profiles(slug: str) -> list[RelationshipChemistryProfile]:
    root = project_root(slug) / CHEMISTRY_DIR
    if not project_root(slug).exists():
        raise FileNotFoundError(slug)
    if not root.exists():
        return []
    profiles: list[RelationshipChemistryProfile] = []
    for path in sorted(root.glob("*.json")):
        relative = str(path.relative_to(project_root(slug))).replace("\\", "/")
        profile = _load_profile_path(slug, relative)
        if profile is not None:
            profiles.append(profile)
    profiles.sort(key=lambda item: item.updated_at, reverse=True)
    return profiles


def get_chemistry_profile(slug: str, participants: list[str]) -> RelationshipChemistryProfile | None:
    return _load_profile_path(slug, chemistry_path(participants))


def save_chemistry_profile(
    slug: str,
    profile: RelationshipChemistryProfile,
) -> tuple[RelationshipChemistryProfile, str]:
    participants = normalize_participants(profile.participants)
    saved = profile.model_copy(update={"participants": participants, "updated_at": utc_now()})
    path = chemistry_path(participants)
    save_text(slug, path, json.dumps(saved.model_dump(), indent=2, ensure_ascii=False))
    return saved, path


def _render_profile(profile: RelationshipChemistryProfile) -> str:
    lines = [
        f"### Chemistry: {' + '.join(profile.participants)}",
        f"Dynamic: {profile.dynamic_summary or '(not yet established)'}",
        f"Attraction language: {profile.attraction_language or '(not yet established)'}",
        f"Verbal rhythm: {profile.verbal_rhythm or '(not yet established)'}",
        f"Initiation style: {profile.initiation_style or '(not yet established)'}",
        f"Response style: {profile.response_style or '(not yet established)'}",
        f"Power dynamic: {profile.power_dynamic or '(not yet established)'}",
        f"Trust: {profile.trust_state or '(not yet established)'}",
        f"Vulnerability pressure: {profile.vulnerability_pressure or '(not yet established)'}",
    ]
    for label, values in (
        ("Established patterns", profile.established_patterns),
        ("Author-controlled boundaries", profile.boundaries),
        ("Signature elements", profile.signature_elements),
        ("Lore/magic resonance", profile.lore_resonance),
        ("Aftermath needs", profile.aftermath_needs),
        ("Next meaningful escalations", profile.next_escalations),
        ("Avoid", profile.avoidances),
    ):
        if values:
            lines.append(f"{label}: " + "; ".join(values))
    if profile.milestones:
        lines.append("Relationship milestones:")
        for item in profile.milestones[-12:]:
            source = f" ({item.source_path})" if item.source_path else ""
            lines.append(f"- {item.label}: {item.consequence}{source}")
    if profile.author_notes:
        lines.append(f"Author notes: {profile.author_notes}")
    return "\n".join(lines)


def build_chemistry_context(slug: str, names: list[str]) -> tuple[str, list[str]]:
    wanted = {name.casefold() for name in names if name.strip()}
    if len(wanted) < 2:
        return "", []
    selected: list[tuple[RelationshipChemistryProfile, str]] = []
    for profile in list_chemistry_profiles(slug):
        members = {name.casefold() for name in profile.participants}
        if len(members & wanted) >= 2 and members.issubset(wanted):
            selected.append((profile, chemistry_path(profile.participants)))
    if not selected:
        return "", []
    text = "## Relationship chemistry\n" + "\n\n".join(_render_profile(item[0]) for item in selected)
    return text, [item[1] for item in selected]


async def infer_chemistry(slug: str, request: ChemistryInferRequest) -> dict[str, Any]:
    participants = normalize_participants(request.participants)
    query = " ".join(participants + [request.author_direction])
    context, context_files = compile_context(slug, prompt=query)
    memory = build_memory_context(slug, query=query, limit=50)
    characters = build_character_context(slug, participants)
    existing = get_chemistry_profile(slug, participants)
    existing_text = _render_profile(existing) if existing is not None else "(No existing chemistry profile.)"

    user_message = f"""PARTICIPANTS
{', '.join(participants)}

AUTHOR DIRECTION
{request.author_direction or '(No additional direction. Infer only from established material.)'}

EXISTING CHEMISTRY
{existing_text}

CHARACTER CONTEXT
{characters or '(No structured character context.)'}

NARRATIVE MEMORY
{memory or '(No structured narrative memory.)'}

PROJECT / MANUSCRIPT CONTEXT
{context or '(No additional project context.)'}
"""
    raw = await generate(
        request.provider,
        [
            {"role": "system", "content": CHEMISTRY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.35,
        top_p=0.9,
        json_mode=True,
    )
    profile = RelationshipChemistryProfile.model_validate(
        _parse_json_object(raw, "Chemistry analyst")
    )
    profile = profile.model_copy(update={"participants": participants})
    saved_path: str | None = None
    if request.save:
        profile, saved_path = save_chemistry_profile(slug, profile)
    return {
        "profile": profile,
        "saved_path": saved_path,
        "context_files": list(dict.fromkeys(context_files)),
    }


async def analyze_aftermath(slug: str, request: AftermathAnalyzeRequest) -> AftermathProposal:
    participants = [name.strip() for name in request.participants if name.strip()]
    if participants:
        participants = normalize_participants(participants)
    chemistry_text, _ = build_chemistry_context(slug, participants) if len(participants) >= 2 else ("", [])
    character_text = build_character_context(slug, participants) if participants else ""
    source_order = chapter_order(request.source_path) if request.source_path else 0

    user_message = f"""SOURCE
{request.source_path or '(unsaved/current scene)'}

EXPECTED PARTICIPANTS
{', '.join(participants) or '(infer from scene, but include only clear participants)'}

EXISTING CHARACTER STATE
{character_text or '(No participant-specific structured state.)'}

EXISTING RELATIONSHIP CHEMISTRY
{chemistry_text or '(No saved chemistry profile for these participants.)'}

COMPLETED SCENE
{request.scene_text}
"""
    raw = await generate(
        request.provider,
        [
            {"role": "system", "content": AFTERMATH_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.25,
        top_p=0.9,
        json_mode=True,
    )
    proposal = AftermathProposal.model_validate(_parse_json_object(raw, "Aftermath analyst"))
    return proposal.model_copy(
        update={
            "source_path": request.source_path,
            "chapter_order": source_order,
        }
    )


def _extend_unique(existing: list[str], additions: list[str]) -> list[str]:
    result = list(existing)
    seen = {item.casefold() for item in existing}
    for item in additions:
        cleaned = item.strip()
        if cleaned and cleaned.casefold() not in seen:
            result.append(cleaned)
            seen.add(cleaned.casefold())
    return result


def apply_aftermath(slug: str, proposal: AftermathProposal) -> tuple[list[RelationshipChemistryProfile], list[str]]:
    profiles: list[RelationshipChemistryProfile] = []
    paths: list[str] = []
    for update in proposal.relationship_updates:
        participants = normalize_participants(update.participants)
        current = get_chemistry_profile(slug, participants) or RelationshipChemistryProfile(
            participants=participants
        )
        milestones = list(current.milestones)
        if update.milestone_label.strip():
            milestones.append(
                ChemistryMilestone(
                    label=update.milestone_label.strip(),
                    consequence=update.milestone_consequence.strip(),
                    source_path=proposal.source_path,
                    chapter_order=proposal.chapter_order,
                )
            )
        revised = current.model_copy(
            update={
                "dynamic_summary": update.dynamic_summary.strip() or current.dynamic_summary,
                "trust_state": update.trust_state.strip() or current.trust_state,
                "vulnerability_pressure": (
                    update.vulnerability_pressure.strip() or current.vulnerability_pressure
                ),
                "established_patterns": _extend_unique(
                    current.established_patterns, update.add_established_patterns
                ),
                "signature_elements": _extend_unique(
                    current.signature_elements, update.add_signature_elements
                ),
                "lore_resonance": _extend_unique(
                    current.lore_resonance, update.add_lore_resonance
                ),
                "aftermath_needs": _extend_unique(
                    current.aftermath_needs, update.add_aftermath_needs
                ),
                "next_escalations": [item.strip() for item in update.next_escalations if item.strip()]
                or current.next_escalations,
                "milestones": milestones[-100:],
            }
        )
        saved, path = save_chemistry_profile(slug, revised)
        profiles.append(saved)
        paths.append(path)
    return profiles, paths
