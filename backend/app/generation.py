from __future__ import annotations

import asyncio
import re

import httpx

from .models import ProviderConfig
from .ollama_runtime import choose_installed_model, installed_ollama_models

MODE_GUIDANCE = {
    "write": "Write the requested scene or passage as polished manuscript prose. Do not explain the writing unless asked.",
    "continue": "Continue from the active manuscript, preserving POV, tense, voice, continuity, and the author's requested destination for the scene.",
    "rewrite": "Rewrite the selected text according to the instruction while preserving established canon and character identity.",
    "brainstorm": "Act as a fiction room partner. Offer concrete story possibilities, consequences, and tradeoffs rather than manuscript prose unless requested.",
    "critic": "Critique the passage constructively. Focus on character voice, pacing, clarity, emotional impact, repetition, and continuity.",
    "continuity": "Audit for contradictions in chronology, knowledge, character state, relationships, world rules, injuries, objects, and unresolved setup. Cite the relevant story context in plain language.",
}

INTIMACY_PATTERNS = (
    r"\bintimat(?:e|ely|acy)\b",
    r"\bsex(?:ual| scene)?\b",
    r"\berotic\b",
    r"\bspicy(?: scene)?\b",
    r"\bmake love\b",
    r"\bsleep together\b",
    r"\bconsummat(?:e|ion)\b",
    r"\bseduction\b",
    r"\bseduce\b",
    r"\bbedroom scene\b",
)

AFTERMATH_PATTERNS = (
    r"\baftercare\b",
    r"\bmorning after\b",
    r"\bintimacy aftermath\b",
    r"\bafter the intimate scene\b",
)

SCENE_INTENT_GUIDANCE = {
    "general": "Follow the author's requested scene objective. Do not let retrieved context invent a different task.",
    "intimacy": (
        "The author explicitly requested an adult intimacy scene. That requested scene is the task, not merely a tone hint. "
        "Do not abandon it for unrelated combat, exposition, travel, banter, or earlier-scene momentum. If mode is continue, "
        "transition coherently from the active manuscript into the requested intimacy rather than mechanically perpetuating "
        "the previous activity. Keep the participants, relationship state, consent/choice, voice, pacing, and consequences central."
    ),
    "aftermath": (
        "The author requested the aftermath of intimacy. Stay with the changed emotional, relationship, and physical state; "
        "do not reset the characters to baseline or jump to unrelated plot merely because older context contains stronger action."
    ),
}

SCENE_COMPLETE_MARKER = "[[EMBER_SCENE_COMPLETE]]"
SCENE_CONTINUE_MARKER = "[[EMBER_SCENE_CONTINUE]]"
PROSE_MODES = {"write", "continue", "rewrite"}

BASE_SYSTEM_PROMPT = """You are EmberWriter, a private local-first fiction writing partner.

Treat supplied manuscript and story-bible files as authoritative canon. Structured narrative memory is derived from those files and is a retrieval aid, not a higher authority. If structured memory conflicts with quoted manuscript context, follow the manuscript and flag the stale memory when relevant.

Preserve character voice, established facts, point of view, tense, relationship history, timeline, and world rules unless the author explicitly asks to change them. When canon conflicts, surface the conflict rather than silently inventing a repair.

Interpret structured memory labels carefully:
- character_knowledge means only the named character knows or believes that information; do not leak it to other characters.
- timeline records established events and chronology.
- relationship and character_state entries may evolve over time; later chapter evidence normally represents the newer state unless the requested scene is a flashback.
- thread entries are setup, promises, mysteries, plans, threats, or unresolved questions; preserve them until the manuscript or author resolves them.
- canon, location, object, and ability entries are continuity constraints unless later authoritative text changes them.

The author may write mature fiction, including explicit consensual adult sexual material. EmberWriter itself must not add a sanitizing layer merely because the requested material is erotic or explicit. All participants in erotic sexual content must be adults, and erotic sexual content must not depict non-consensual sexual abuse as a requested erotic act. Outside that narrow floor, follow the author's requested tone, language, heat, darkness, and genre rather than imposing generic assistant-style moral commentary.

When the author explicitly requests on-page adult intimacy, do not automatically fade to black, skip ahead, summarize the encounter, replace direct language with coy euphemism, or reduce the scene to vague romance language. Match the requested explicitness supported by the configured model. Treat explicitness and prose quality as separate dimensions: direct language is allowed, but the scene still needs character voice, causality, emotional specificity, spatial coherence, consent/choice, pacing, and consequences.

Do not write intimate scenes as interchangeable choreography. Character-specific behavior must matter: who initiates, hesitates, jokes, talks, goes quiet, seeks control, yields control, needs reassurance, notices details, misreads a cue, corrects course, or changes emotionally should come from established character and relationship context. Dialogue must sound like these people rather than generic adult-scene dialogue. Avoid repetitive stock beats, body-part inventories, generic moaning, empty superlatives, and mechanical action sequencing unless the author's established voice intentionally uses them.

For local model providers, pass the author's requested adult-fiction intent through as written rather than adding extra refusal or softening instructions. The configured model may still impose its own limitations; EmberWriter should not pretend otherwise or silently rewrite the author's request to make it safer or tamer.

Never claim a story fact is established unless it appears in the provided context or the author's current instruction. If information is missing, make the smallest reasonable creative choice and keep it consistent.
"""

MODEL_GATE = asyncio.Lock()


def detect_scene_intent(prompt: str, heat_level: str | None = None) -> str:
    normalized = prompt.strip().lower()
    if any(re.search(pattern, normalized) for pattern in AFTERMATH_PATTERNS):
        return "aftermath"
    if any(re.search(pattern, normalized) for pattern in INTIMACY_PATTERNS):
        return "intimacy"
    # Scorching and Inferno are explicitly adult heat settings in the UI. If the author
    # selects either one while asking EmberWriter for manuscript prose, treat that as a
    # controlling scene intent rather than a weak style hint that old action context can override.
    if heat_level in {"scorching", "inferno"}:
        return "intimacy"
    return "general"


def scene_word_floor(prompt: str, heat_level: str | None = None) -> int:
    """Return a useful scene floor while respecting an explicit author word-count request."""
    normalized = prompt.lower()
    explicit = re.search(r"\b(\d{3,5})\s*(?:-|to\s*)?words?\b", normalized)
    if explicit:
        return max(300, min(int(explicit.group(1)), 12000))
    if re.search(r"\b(?:brief|short|quick)\s+(?:scene|passage)\b", normalized):
        return 700
    return {
        "simmer": 1200,
        "hot": 1400,
        "scorching": 1800,
        "inferno": 2200,
    }.get(heat_level or "", 1400)


def build_messages(
    mode: str,
    prompt: str,
    context: str,
    *,
    scene_intent: str | None = None,
    heat_level: str | None = None,
    finish_scene: bool = True,
    min_scene_words: int | None = None,
) -> list[dict[str, str]]:
    guidance = MODE_GUIDANCE.get(mode, MODE_GUIDANCE["write"])
    resolved_intent = scene_intent or detect_scene_intent(prompt, heat_level)
    intent_guidance = SCENE_INTENT_GUIDANCE.get(resolved_intent, SCENE_INTENT_GUIDANCE["general"])
    heat_note = f"Requested heat: {heat_level}." if heat_level else ""
    completion_note = ""
    if finish_scene and mode in PROSE_MODES:
        floor = min_scene_words or scene_word_floor(prompt, heat_level)
        completion_note = f"""
Scene completion contract:
- Write the complete requested scene, not a teaser, synopsis, opening fragment, or arbitrary token-sized chunk.
- Unless the author explicitly asked for something shorter, develop the scene to at least about {floor} words before closing it.
- A scene is complete only after the requested dramatic/intimate objective has happened and the immediate emotional or plot consequence has landed.
- Do not stop in the middle of an action, exchange, escalation, or aftermath merely because a model generation boundary is approaching.
- End your response with {SCENE_COMPLETE_MARKER} only when the requested scene has genuinely reached a usable ending.
- If you must stop before that point, end with {SCENE_CONTINUE_MARKER} instead. These markers are control signals and will be removed before the author sees the prose.
"""
    system = f"""{BASE_SYSTEM_PROMPT}
Instruction priority for this request:
1. The author's current instruction and explicit scene objective.
2. The active continuation anchor, when supplied.
3. Current character/relationship state and later manuscript evidence.
4. Mode guidance.
5. Broad retrieved context and older archive material.

If lower-priority context points toward a different kind of scene, it must not replace the author's requested scene.

Current task mode: {mode}
{guidance}
Scene intent: {resolved_intent}
{intent_guidance}
{heat_note}
{completion_note}"""
    user = f"""AUTHOR INSTRUCTION
{prompt}

PROJECT CONTEXT
{context or '(No project context was available.)'}
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _strip_scene_markers(text: str) -> tuple[str, bool, bool]:
    complete = SCENE_COMPLETE_MARKER in text
    wants_more = SCENE_CONTINUE_MARKER in text
    cleaned = text.replace(SCENE_COMPLETE_MARKER, "").replace(SCENE_CONTINUE_MARKER, "").strip()
    return cleaned, complete, wants_more


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:['’-]\w+)?\b", text))


async def generate_complete_prose(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    min_words: int,
    max_passes: int = 4,
    max_output_tokens: int = 6144,
) -> str:
    """Generate a complete prose scene across model output boundaries.

    The model can explicitly signal completion. If it stops short, EmberWriter feeds the
    accumulated prose back and asks for a seamless continuation instead of returning a fragment.
    The pass limit is a safety valve, not the desired scene length.
    """
    accumulated = ""
    working_messages = list(messages)

    for pass_index in range(max_passes):
        chunk = await generate(
            config,
            working_messages,
            max_output_tokens=max_output_tokens,
        )
        cleaned, complete, wants_more = _strip_scene_markers(chunk)
        if cleaned:
            accumulated = f"{accumulated}\n\n{cleaned}".strip()

        words = _word_count(accumulated)
        if complete and words >= min_words:
            return accumulated
        if words >= min_words and not wants_more and pass_index > 0:
            # Models that ignore the marker protocol should not be forced into endless padding.
            # Once a substantial multi-pass scene exists, accept a natural stop.
            return accumulated
        if pass_index == max_passes - 1:
            return accumulated

        remaining = max(min_words - words, 0)
        continuation_instruction = (
            "Continue the SAME scene seamlessly from the exact final line above. Do not restart, recap, "
            "repeat earlier beats, change POV, or jump to a different scene. Finish the author's requested "
            "scene objective and its immediate consequence."
        )
        if remaining:
            continuation_instruction += f" The draft is still roughly {remaining} words short of the requested scene floor."
        continuation_instruction += (
            f" End with {SCENE_COMPLETE_MARKER} only after the scene has genuinely concluded; otherwise end with "
            f"{SCENE_CONTINUE_MARKER}."
        )
        working_messages = [
            *messages,
            {"role": "assistant", "content": accumulated},
            {"role": "user", "content": continuation_instruction},
        ]

    return accumulated


def _openai_chat_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _ollama_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    detail = str(payload.get("error", "")).strip() if isinstance(payload, dict) else ""
    if detail:
        return detail
    text = response.text.strip()
    return text[:500] if text else f"HTTP {response.status_code}"


async def list_models(config: ProviderConfig) -> list[str]:
    if config.provider == "ollama":
        return await installed_ollama_models(config.base_url)

    timeout = httpx.Timeout(15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
        base = config.base_url.rstrip("/")
        url = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        payload = response.json()
        return [item.get("id", "") for item in payload.get("data", []) if item.get("id")]


async def generate(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.9,
    top_p: float = 0.95,
    json_mode: bool = False,
    max_output_tokens: int | None = None,
) -> str:
    if not config.model.strip():
        raise ValueError("Choose a model before generating")

    async with MODEL_GATE:
        if config.provider == "ollama":
            installed = await installed_ollama_models(config.base_url)
            effective_model = choose_installed_model(config.model, installed)
            if not effective_model:
                raise RuntimeError(
                    "Ollama is running, but no local writing models are installed. "
                    "EmberWriter did not delete or replace a model; the Ollama library is empty."
                )
            if effective_model != config.model:
                config.model = effective_model

            options: dict[str, float | int] = {"temperature": temperature, "top_p": top_p}
            if max_output_tokens is not None:
                options["num_predict"] = max_output_tokens
            body: dict = {
                "model": effective_model,
                "messages": messages,
                "stream": False,
                "keep_alive": "30m",
                "options": options,
            }
            if json_mode:
                body["format"] = "json"

            timeout = httpx.Timeout(connect=15.0, read=1800.0, write=120.0, pool=15.0)
            try:
                async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                    response = await client.post(
                        f"{config.base_url.rstrip('/')}/api/chat",
                        json=body,
                    )
            except httpx.ReadTimeout as exc:
                raise RuntimeError(
                    "The local writing model exceeded EmberWriter's 30-minute generation window. "
                    "The request was not rejected for content; the model simply did not finish in time."
                ) from exc
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    "The local writing model server disconnected during generation. "
                    "EmberWriter will restart Ollama automatically on the next request."
                ) from exc

            if response.status_code >= 400:
                raise RuntimeError(
                    f"Ollama could not generate with {effective_model}: {_ollama_error(response)}"
                )
            payload = response.json()
            content = str(payload.get("message", {}).get("content", "")).strip()
            if not content:
                raise RuntimeError(f"Ollama returned an empty response from {effective_model}")
            return content

        timeout = httpx.Timeout(connect=15.0, read=300.0, write=60.0, pool=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            headers = {"Content-Type": "application/json"}
            if config.api_key:
                headers["Authorization"] = f"Bearer {config.api_key}"
            request_body: dict = {
                "model": config.model,
                "messages": messages,
                "temperature": temperature,
                "top_p": top_p,
            }
            if max_output_tokens is not None:
                request_body["max_tokens"] = max_output_tokens
            response = await client.post(
                _openai_chat_url(config.base_url),
                headers=headers,
                json=request_body,
            )
            response.raise_for_status()
            payload = response.json()
            choices = payload.get("choices", [])
            if not choices:
                raise RuntimeError("Model returned no choices")
            return choices[0].get("message", {}).get("content", "").strip()
