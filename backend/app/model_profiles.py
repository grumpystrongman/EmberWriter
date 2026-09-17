from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelProfile:
    key: str
    title: str
    model: str
    purpose: str
    why: str
    best_for: tuple[str, ...]
    avoid_for: tuple[str, ...]
    temperature: float
    top_p: float
    top_k: int
    min_p: float
    repeat_penalty: float
    repeat_last_n: int
    presence_penalty: float = 0.0


MODEL_PROFILES: tuple[ModelProfile, ...] = (
    ModelProfile(
        key="mature",
        title="Mature / relationship fiction",
        model="HammerAI/rocinante-v1.1:12b-q4_K_M",
        purpose="Character-led mature fiction, romance, harem, kink, and roleplay-heavy scenes.",
        why=(
            "Rocinante is a 12B story/RP model rather than a merely decensored instruction model. "
            "Its model card emphasizes richer prose, creativity, storytelling, and RP/story templates."
        ),
        best_for=("adult relationship scenes", "harem / kink fiction", "romance", "character voice", "dialogue-heavy scenes"),
        avoid_for=("continuity audits", "structured analysis", "technical research"),
        temperature=0.72,
        top_p=0.90,
        top_k=40,
        min_p=0.05,
        repeat_penalty=1.03,
        repeat_last_n=128,
    ),
    ModelProfile(
        key="general",
        title="General fiction",
        model="ministral-3:14b",
        purpose="Regular chapters, action, dialogue, worldbuilding, revision, and non-erotic fiction.",
        why=(
            "Ministral 3 has strong instruction following, a large context window, and is a better default when "
            "the scene does not depend on RP/NSFW specialization."
        ),
        best_for=("general chapters", "action", "dialogue", "worldbuilding", "rewrites", "mixed-genre fiction"),
        avoid_for=("specialized explicit RP when Rocinante is available",),
        temperature=0.78,
        top_p=0.90,
        top_k=40,
        min_p=0.03,
        repeat_penalty=1.02,
        repeat_last_n=128,
    ),
    ModelProfile(
        key="planning",
        title="Planning / story logic",
        model="qwen3:8b",
        purpose="Brainstorming, outlining, continuity, critique, alternatives, and story problem-solving.",
        why=(
            "Qwen3 is strong at instruction following and reasoning. It is useful as a story-room model, "
            "but it is not EmberWriter's preferred final-prose model."
        ),
        best_for=("brainstorming", "outlining", "continuity", "critique", "plot alternatives"),
        avoid_for=("final intimate prose", "voice-sensitive final chapters"),
        temperature=0.70,
        top_p=0.80,
        top_k=20,
        min_p=0.0,
        repeat_penalty=1.0,
        repeat_last_n=64,
        presence_penalty=1.5,
    ),
)


def profile_for_model(model: str) -> ModelProfile | None:
    name = model.casefold()
    if "rocinante" in name or "rudy-nemo" in name:
        return MODEL_PROFILES[0]
    if "stheno" in name:
        return ModelProfile(
            key="mature-fast",
            title="Mature / fast",
            model=model,
            purpose="Fast mature roleplay and storywriting on lighter hardware.",
            why="Stheno is trained on both SFW and NSFW storywriting and roleplay data.",
            best_for=("fast mature drafts", "roleplay", "dialogue"),
            avoid_for=("very long-context projects",),
            temperature=1.16,
            top_p=0.95,
            top_k=50,
            min_p=0.075,
            repeat_penalty=1.10,
            repeat_last_n=64,
        )
    if "ministral-3" in name or "mistral-small" in name:
        return MODEL_PROFILES[1]
    if "qwen3" in name:
        return MODEL_PROFILES[2]
    if "qwen2.5" in name or "qwen2" in name:
        return ModelProfile(
            key="legacy-qwen",
            title="Legacy Qwen instruct",
            model=model,
            purpose="General instruction following; retained for compatibility.",
            why="Useful general instruct model, but not the preferred specialist for final fiction in EmberWriter.",
            best_for=("general instructions", "analysis"),
            avoid_for=("specialized mature fiction",),
            temperature=0.70,
            top_p=0.80,
            top_k=20,
            min_p=0.0,
            repeat_penalty=1.05,
            repeat_last_n=64,
        )
    return None


def ollama_sampling_options(
    model: str,
    *,
    temperature: float,
    top_p: float,
    json_mode: bool = False,
) -> dict[str, float | int]:
    """Return model-aware sampler settings without overriding low-temp verifier calls."""
    profile = profile_for_model(model)
    if profile is None:
        return {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": 40,
            "repeat_penalty": 1.03,
            "repeat_last_n": 128,
        }

    # JSON/verifier/editor calls deliberately pass low temperatures; preserve that request while
    # still using the model's safer token filtering and repetition behavior.
    effective_temperature = temperature if json_mode or temperature <= 0.5 else profile.temperature
    effective_top_p = top_p if json_mode or temperature <= 0.5 else profile.top_p
    options: dict[str, float | int] = {
        "temperature": effective_temperature,
        "top_p": effective_top_p,
        "top_k": profile.top_k,
        "min_p": profile.min_p,
        "repeat_penalty": profile.repeat_penalty,
        "repeat_last_n": profile.repeat_last_n,
    }
    if profile.presence_penalty:
        options["presence_penalty"] = profile.presence_penalty
    return options


def profile_catalog() -> list[dict[str, object]]:
    return [
        {
            "key": item.key,
            "title": item.title,
            "model": item.model,
            "purpose": item.purpose,
            "why": item.why,
            "best_for": list(item.best_for),
            "avoid_for": list(item.avoid_for),
        }
        for item in MODEL_PROFILES
    ]
