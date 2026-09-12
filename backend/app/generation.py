from __future__ import annotations

import asyncio

import httpx

from .models import ProviderConfig

MODE_GUIDANCE = {
    "write": "Write the requested scene or passage as polished manuscript prose. Do not explain the writing unless asked.",
    "continue": "Continue directly from the active manuscript, preserving POV, tense, voice, continuity, and scene momentum.",
    "rewrite": "Rewrite the selected text according to the instruction while preserving established canon and character identity.",
    "brainstorm": "Act as a fiction room partner. Offer concrete story possibilities, consequences, and tradeoffs rather than manuscript prose unless requested.",
    "critic": "Critique the passage constructively. Focus on character voice, pacing, clarity, emotional impact, repetition, and continuity.",
    "continuity": "Audit for contradictions in chronology, knowledge, character state, relationships, world rules, injuries, objects, and unresolved setup. Cite the relevant story context in plain language.",
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


def build_messages(mode: str, prompt: str, context: str) -> list[dict[str, str]]:
    guidance = MODE_GUIDANCE.get(mode, MODE_GUIDANCE["write"])
    system = f"{BASE_SYSTEM_PROMPT}\nCurrent task mode: {mode}\n{guidance}"
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


async def list_models(config: ProviderConfig) -> list[str]:
    timeout = httpx.Timeout(15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        if config.provider == "ollama":
            response = await client.get(f"{config.base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            payload = response.json()
            return [item.get("name", "") for item in payload.get("models", []) if item.get("name")]

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
        timeout = httpx.Timeout(connect=15.0, read=300.0, write=60.0, pool=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            if config.provider == "ollama":
                body: dict = {
                    "model": config.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature, "top_p": top_p},
                }
                if json_mode:
                    body["format"] = "json"
                response = await client.post(
                    f"{config.base_url.rstrip('/')}/api/chat",
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
                return payload.get("message", {}).get("content", "").strip()

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
