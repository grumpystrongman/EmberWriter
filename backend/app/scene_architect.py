from __future__ import annotations

import json
import re
from typing import Any
from uuid import uuid4

from .generation import generate
from .models import ScenePlan, ScenePlanRequest
from .storage import compile_context, save_text, utc_now
from .story_intelligence import build_character_context, build_story_intelligence

SCENE_ARCHITECT_SYSTEM_PROMPT = """You are EmberWriter's Scene Architect.
Return ONLY valid JSON for a practical scene plan that an author can use to write the next scene.

Use the supplied manuscript, story memory, character knowledge, relationship state, and author instruction as constraints. The manuscript and explicit author instruction outrank derived memory if they conflict.

Planning rules:
- Do not invent established canon when the context is silent; phrase optional inventions as scene choices instead.
- Protect point-of-view knowledge boundaries. A character cannot act on information they have not learned.
- Prefer causal beats: each beat should change pressure, knowledge, emotion, relationship, or goal state.
- Carry unresolved setup/payoff forward when relevant without forcing every open thread into one scene.
- Relationship movement should be specific to the participants and earned by the scene.
- If intimacy is requested, treat it as character/relationship development with consequences and preserve established adult/consent constraints.
- The ending should create a changed state or meaningful pressure for what follows.
- Keep beats concise enough to scan while drafting.

Return exactly this JSON shape:
{
  "title": "short working scene title",
  "pov": "POV character or narrative mode",
  "participants": ["character"],
  "location": "location",
  "scene_objective": "what this scene must accomplish",
  "conflict": "the main source of resistance or tension",
  "opening_state": "important starting physical/emotional/story state",
  "beats": [
    {
      "beat": "what happens",
      "purpose": "why the beat exists",
      "character_shift": "what changes internally/interpersonally"
    }
  ],
  "emotional_arc": "emotional movement across the scene",
  "relationship_moves": ["specific relationship change to earn or test"],
  "reveals": ["information legitimately revealed in this scene"],
  "continuity_requirements": ["fact, injury, knowledge boundary, promise, object, or world rule to preserve"],
  "unresolved_threads": ["relevant setup/payoff carried into or out of the scene"],
  "intimacy_notes": ["character-specific intimacy/romance notes when relevant; otherwise empty"],
  "ending_state": "how the story/characters are different at scene end",
  "next_scene_pressure": "pressure or question created for the next scene"
}
"""


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Scene Architect did not return a JSON object")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("Scene Architect returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise TypeError("Scene Architect returned an invalid payload")
    return payload


def _relationship_context(slug: str, participants: list[str]) -> str:
    intelligence = build_story_intelligence(slug)
    wanted = {name.casefold() for name in participants if name.strip()}
    edges = intelligence["relationships"]
    if wanted:
        edges = [
            edge
            for edge in edges
            if edge["source"].casefold() in wanted or edge["target"].casefold() in wanted
        ]
    if not edges:
        return ""
    lines = ["## Relevant relationship history"]
    for edge in edges[:30]:
        detail = f" — {edge['detail']}" if edge["detail"] else ""
        lines.append(
            f"- {edge['source']} -> {edge['target']}: {edge['state']}{detail} "
            f"(ch {edge['chapter_order'] or '?'}, {edge['source_path']})"
        )
    return "\n".join(lines)


async def create_scene_plan(slug: str, request: ScenePlanRequest) -> dict[str, Any]:
    prompt_bits = [request.prompt, request.pov, request.location, *request.participants]
    context, context_files = compile_context(
        slug,
        prompt=" ".join(bit for bit in prompt_bits if bit),
        active_file=request.active_file,
    )
    character_context = build_character_context(slug, request.participants)
    relationship_context = _relationship_context(slug, request.participants)

    user_message = f"""AUTHOR'S SCENE REQUEST
{request.prompt}

AUTHOR-SPECIFIED CONSTRAINTS
POV: {request.pov or '(choose from context)'}
Participants: {', '.join(request.participants) or '(infer only obvious participants)'}
Location: {request.location or '(infer only if established or clearly requested)'}
Desired heat/intimacy level: {request.desired_heat}

CHARACTER STATE
{character_context or '(No participant-specific structured state was found.)'}

RELATIONSHIP STATE
{relationship_context or '(No structured relationship state was found.)'}

PROJECT CONTEXT
{context or '(No additional project context was available.)'}
"""

    raw = await generate(
        request.provider,
        [
            {"role": "system", "content": SCENE_ARCHITECT_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.45,
        top_p=0.9,
        json_mode=True,
    )
    plan = ScenePlan.model_validate(_parse_json_object(raw))
    saved_path: str | None = None

    if request.save:
        saved_path = f"scenes/scene-plan-{uuid4().hex[:10]}.json"
        artifact = {
            "schema_version": 1,
            "generated_at": utc_now(),
            "author_request": request.prompt,
            "active_file": request.active_file,
            "plan": plan.model_dump(),
        }
        save_text(slug, saved_path, json.dumps(artifact, indent=2, ensure_ascii=False))

    return {
        "plan": plan,
        "saved_path": saved_path,
        "context_files": context_files,
    }
