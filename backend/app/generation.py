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


def detect_scene_intent(prompt: str) -> str:
    normalized = prompt.strip().lower()
    if any(re.search(pattern, normalized) for pattern in AFTERMATH_PATTERNS):
        return "aftermath"
    if any(re.search(pattern, normalized) for pattern in INTIMACY_PATTERNS):
        return "intimacy"
    return "general"


def build_messages(
    mode: str,
    prompt: str,
    context: str,
    *,
    scene_intent: str | None = None,
    heat_level: str | None = None,
) -> list[dict[str, str]]:
    guidance = MODE_GUIDANCE.get(mode, MODE_GUIDANCE["write"])
    resolved_intent = scene_intent or detect_scene_intent(prompt)
    intent_guidance = SCENE_INTENT_GUIDANCE.get(resolved_intent, SCENE_INTENT_GUIDANCE["general"])
    heat_note = f"Requested heat: {heat_level}." if heat_level else ""
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
{heat_note}"""
    user = f"""AUTHOR INSTRUCTION
{prompt}

PROJECT CONTEXT
{context or '(No project context was available.)'}
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


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
                # Repair stale browser state for this request. The next /models refresh will
                # write the same installed model back to localStorage in the frontend.
                config.model = effective_model

            body: dict = {
                "model": effective_model,
                "messages": messages,
                "stream": False,
                "keep_alive": "30m",
                "options": {"temperature": temperature, "top_p": top_p},
            }
            if json_mode:
                body["format"] = "json"

            # Deep dossier/analysis jobs can legitimately run for many minutes on a
            # 14B local model. The old five-minute read timeout surfaced as the blank
            # `Model server error:` toast seen in Character Studio. Give local work a
            # real long-form window while retaining bounded connect/write timeouts.
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
            response = await client.post(
                _openai_chat_url(config.base_url),
                headers=headers,
                json={
                    "model": config.model,
                    "messages": messages,
                    "temperature": temperature,
                    "top_p": top_p,
                },
            )
            response.raise_for_status()
            payload = response.json()
            choices = payload.get("choices", [])
            if not choices:
                raise RuntimeError("Model returned no choices")
            return choices[0].get("message", {}).get("content", "").strip()
