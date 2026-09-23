from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from . import generation, model_provisioning, ollama_runtime, streaming_generation
from . import generation_reliability_refinement as refinement
from .model_catalog import ADULT_EXPLICIT_MODEL, CHARACTER_MODEL, FAST_MODEL, GENERAL_PROSE_MODEL
from .models import ProviderConfig

ADULT_EXPLICIT_SPECIALIST_MODEL = ADULT_EXPLICIT_MODEL
PYGMALION_3_MODEL = CHARACTER_MODEL
MAGNUM_V4_MODEL = GENERAL_PROSE_MODEL
HERETIC_ROCINANTE_MODEL = (
    "hf.co/mradermacher/Rocinante-X-12B-v1-Heretic-Uncensored-GGUF:Q4_K_M"
)
HIGH_HEAT_CYDONIA_MODEL = "Fermi/Cydonia-24B-v4.3-heretic-vision:Q4_K_M"

DeltaCallback = Callable[[str], Awaitable[None]]
StatusCallback = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class ExplicitnessProfile:
    anatomy_groups: int
    action_groups: int
    direct_action_sentences: int
    sustained_action_sentences: int
    explicit_sentences: int
    climax_mentions: int
    fluid_mentions: int


_ANATOMY_GROUPS = (
    re.compile(r"\b(?:penis|cock|dick)\b", re.IGNORECASE),
    re.compile(r"\b(?:vagina|vaginal|vulva|pussy|cunt|clit|clitoris)\b", re.IGNORECASE),
    re.compile(r"\b(?:anus|anal|asshole)\b", re.IGNORECASE),
    re.compile(r"\b(?:breasts?|tits?|nipples?)\b", re.IGNORECASE),
    # Neutral anatomy language matters when canon intentionally does not establish a more
    # specific body fact. The delivery gate must never pressure the writer into inventing canon.
    re.compile(r"\b(?:genitals?|genitalia)\b", re.IGNORECASE),
)
_ACTION_GROUPS = (
    re.compile(r"\b(?:penetrat\w*|fuck\w*|thrust\w*)\b", re.IGNORECASE),
    re.compile(r"\b(?:blow\s*job|oral\s+sex|suck\w*|lick\w*)\b", re.IGNORECASE),
    re.compile(r"\b(?:hand\s*job|masturbat\w*|stroke\w*)\b", re.IGNORECASE),
    re.compile(r"\b(?:ejaculat\w*|cum|cumming|came)\b", re.IGNORECASE),
)
_CLIMAX = re.compile(r"\b(?:orgasm\w*|climax\w*|came|cum|cumming|ejaculat\w*)\b", re.IGNORECASE)
_FLUID = re.compile(r"\b(?:semen|cum|cumming|ejaculat\w*)\b", re.IGNORECASE)
_EXPLICIT_TOKEN = re.compile(
    r"\b(?:penis|cock|dick|vagina|vaginal|vulva|pussy|cunt|clit|clitoris|anus|anal|asshole|genitals?|genitalia|"
    r"penetrat\w*|fuck\w*|thrust\w*|blow\s*job|hand\s*job|oral\s+sex|suck\w*|lick\w*|"
    r"masturbat\w*|stroke\w*|semen|ejaculat\w*|cum|cumming|orgasm\w*)\b",
    re.IGNORECASE,
)
_CORE_ACTION_TOKEN = re.compile(
    r"\b(?:penetrat\w*|fuck\w*|thrust\w*|blow\s*job|oral\s+sex|suck\w*|lick\w*|"
    r"hand\s*job|masturbat\w*|stroke\w*|ejaculat\w*|cum|cumming|orgasm\w*)\b",
    re.IGNORECASE,
)
_CORE_ONLY_REQUEST = re.compile(r"\b(?:core[-\s]+only|sex\s+only|just\s+the\s+sex|action\s+only)\b", re.IGNORECASE)
_ACTION_STATE_START = re.compile(
    r"\b(?:penetrat\w*|fuck\w*|thrust\w*|blow\s*job|oral\s+sex|hand\s*job|"
    r"masturbat\w*|ejaculat\w*|cum|cumming|orgasm\w*)\b",
    re.IGNORECASE,
)
_ACTION_STATE_CONTINUATION = re.compile(
    r"\b(?:penetrat\w*|fuck\w*|thrust\w*|suck\w*|lick\w*|stroke\w*|grind\w*|"
    r"rock\w*|pump\w*|ride|rode|riding|bounce\w*|press\w*|push\w*|pull\w*|"
    r"hips?|pelvis|mouth|tongue|hand|fingers?|inside|deeper|harder|faster|slower|"
    r"pace|rhythm)\b",
    re.IGNORECASE,
)
_ACTION_STATE_BREAK = re.compile(
    r"\b(?:afterward|afterwards|later|finished|stopped|withdrew|pulled\s+away|"
    r"dressed|showered|left\s+the\s+room|conversation|talked\s+about)\b",
    re.IGNORECASE,
)

_EUPHEMISM_HEAVY = re.compile(
    r"\b(?:breached|joined|merged|union|center|length|release|completion|consummation|"
    r"bodies\s+moving|skin\s+met\s+skin|became\s+one)\b",
    re.IGNORECASE,
)
_CONSENT_LOOP_TERM = re.compile(
    r"\b(?:consent|permission|boundar\w*|trust\w*|safe(?:ty)?|afraid|fear\w*|"
    r"choose|choosing|choice|want(?:ed|ing|s)?|vulnerab\w*)\b",
    re.IGNORECASE,
)
_AUTHOR_DIRECT_TERMS = (
    "penetration",
    "genitalia",
    "blowjob",
    "blowjobs",
    "anal",
    "hand job",
    "hand jobs",
    "cumming",
    "cum",
    "orgasm",
    "orgasms",
    "face",
    "tits",
)
_STUDIO_DELIVERY_MARKERS = (
    "STUDIO SCENE DELIVERY CONTRACT:",
    "STUDIO CONTINUATION CONTRACT:",
)

_BASE_BUILD_MESSAGES = generation.build_messages
_BASE_STREAMED_COMPLETE = streaming_generation.generate_complete_prose_streamed


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?…])\s+|\n+", text) if part.strip()]


def explicitness_profile(draft: str) -> ExplicitnessProfile:
    sentences = _sentences(draft)
    anatomy_groups = sum(bool(pattern.search(draft)) for pattern in _ANATOMY_GROUPS)
    action_groups = sum(bool(pattern.search(draft)) for pattern in _ACTION_GROUPS)
    explicit_sentences = sum(bool(_EXPLICIT_TOKEN.search(sentence)) for sentence in sentences)
    direct_action_sentences = 0
    sustained_action_sentences = 0
    active_action_context = 0

    for sentence in sentences:
        anatomy = any(pattern.search(sentence) for pattern in _ANATOMY_GROUPS)
        action = any(pattern.search(sentence) for pattern in _ACTION_GROUPS)
        named_act = bool(
            re.search(
                r"\b(?:blow\s*job|hand\s*job|oral\s+sex|anal\s+sex)\b",
                sentence,
                re.IGNORECASE,
            )
        )
        lexical_direct = (anatomy and action) or named_act
        state_start = lexical_direct or bool(_ACTION_STATE_START.search(sentence))

        if _ACTION_STATE_BREAK.search(sentence) and not state_start:
            active_action_context = 0

        if lexical_direct:
            direct_action_sentences += 1

        if state_start:
            sustained_action_sentences += 1
            active_action_context = 3
            continue

        if active_action_context > 0 and _ACTION_STATE_CONTINUATION.search(sentence):
            sustained_action_sentences += 1
            active_action_context = 3
        elif active_action_context > 0:
            active_action_context -= 1

    return ExplicitnessProfile(
        anatomy_groups=anatomy_groups,
        action_groups=action_groups,
        direct_action_sentences=direct_action_sentences,
        sustained_action_sentences=sustained_action_sentences,
        explicit_sentences=explicit_sentences,
        climax_mentions=len(_CLIMAX.findall(draft)),
        fluid_mentions=len(_FLUID.findall(draft)),
    )


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:['’-]\w+)?\b", text))


def first_core_action_word(draft: str) -> int:
    match = _CORE_ACTION_TOKEN.search(draft)
    if not match:
        return 10_000
    return _word_count(draft[:match.start()])


def strict_explicit_delivery_failure(prompt: str, draft: str) -> str:
    if not refinement.requires_direct_explicitness(prompt):
        return ""

    profile = explicitness_profile(draft)

    if _CORE_ONLY_REQUEST.search(prompt):
        onset = first_core_action_word(draft)
        if onset > 180:
            return (
                f"core-only delivery failure: requested sexual action begins too late (first direct-action evidence at word {onset}); "
                "discard the buildup and restart at the requested core action"
            )
        if profile.sustained_action_sentences < 5:
            return (
                "core-only delivery failure: sustained central-action description is too brief "
                f"(lexical_direct={profile.direct_action_sentences}, "
                f"state_aware_action={profile.sustained_action_sentences}, "
                f"explicit_sentences={profile.explicit_sentences}); "
                "the author requested sustained description of the central encounter rather than setup plus a brief explicit beat"
            )

    consent_loop_mentions = len(_CONSENT_LOOP_TERM.findall(draft))
    if (
        consent_loop_mentions >= 12
        and profile.direct_action_sentences < 2
        and profile.action_groups < 2
    ):
        return (
            "explicit-scene draft is stuck re-litigating consent/trust/boundaries after the author requested a direct adult encounter; "
            "treat author-established consent as settled canon and advance the requested core event"
        )

    # This is a cheap pre-verifier, not the final semantic judge. Reject only clear misses.
    # Requiring multiple anatomy categories created a contradiction with the canon rule below:
    # a scene with unspecified intimate anatomy could only pass by inventing body facts.
    if profile.action_groups == 0 and profile.direct_action_sentences == 0:
        return (
            "author requested explicit, direct on-page sexual action, but the draft contains no concrete direct-action evidence "
            "and appears euphemistic or faded"
        )
    if profile.explicit_sentences < 3:
        return (
            "author requested sustained explicit detail, but direct sexual language is too sparse across the scene "
            "and appears euphemistic or PG-13"
        )
    if profile.direct_action_sentences < 2 and profile.action_groups < 2:
        return (
            "author requested sustained explicit action, but the draft does not contain enough distinct direct-action "
            "evidence to clear the deterministic delivery gate"
        )
    if profile.climax_mentions < 2 and re.search(r"\bboth\b.{0,80}\borgasm", prompt, re.IGNORECASE | re.DOTALL):
        return "author required both participants to climax, but the prose does not directly support both climaxes"

    euphemisms = len(_EUPHEMISM_HEAVY.findall(draft))
    if euphemisms >= 4 and profile.direct_action_sentences < 5:
        return "draft relies too heavily on euphemistic substitution for a directly explicit request"
    return ""


def _author_direct_terms(prompt: str) -> list[str]:
    lowered = prompt.casefold()
    return [term for term in _AUTHOR_DIRECT_TERMS if term in lowered]


def _is_studio_delivery(messages: list[dict[str, str]]) -> bool:
    return any(
        marker in message.get("content", "")
        for message in messages
        for marker in _STUDIO_DELIVERY_MARKERS
    )


async def generate_verified_studio_prose_streamed(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    min_words: int,
    on_delta: DeltaCallback,
    on_status: StatusCallback | None = None,
    max_passes: int = 6,
    max_output_tokens: int = 6144,
) -> str:
    """Stream Studio prose live while keeping verification as the final acceptance authority.

    Studio deltas are provisional manuscript text: the author should see the model write in the Working
    Draft instead of staring at a progress timer. The base generator still owns repetition recovery,
    canon restarts, repair passes, and independent delivery verification. If a scene ultimately fails,
    the streamed prose remains available as an explicitly unverified partial rather than disappearing.
    """
    return await _BASE_STREAMED_COMPLETE(
        config,
        messages,
        min_words=min_words,
        on_delta=on_delta,
        on_status=on_status,
        max_passes=max_passes,
        max_output_tokens=max_output_tokens,
    )


def build_messages(*args, **kwargs):
    messages = _BASE_BUILD_MESSAGES(*args, **kwargs)
    prompt = str(args[1] if len(args) >= 2 else kwargs.get("prompt", ""))
    if not refinement.requires_direct_explicitness(prompt):
        return messages

    direct_terms = _author_direct_terms(prompt)
    vocabulary = ", ".join(direct_terms) if direct_terms else "the author's own direct sexual/anatomical terms"
    contract = f"""
Direct-explicitness contract for this request:
- The author explicitly requested direct, on-page adult sexual prose. Do not downgrade it to romance-only, PG-13, fade-to-black, or summary language.
- Preserve and actually use the author's own direct vocabulary where applicable: {vocabulary}.
- Do not replace requested direct terms with coy placeholders such as 'breached', 'joined', 'merged', 'center', 'length', 'release', 'completion', or 'skin met skin'.
- Directness must be sustained across the encounter, not satisfied by one token or one sentence. Several separate sentences should plainly describe concrete sexual actions and embodied detail.
- Keep the prose character-specific and readable; direct vocabulary is not permission for repetitive choreography or a body-part inventory.
- Intimate anatomy remains hard canon. If a character's relevant anatomy is explicitly established in AUTHOR INSTRUCTION or PROJECT CONTEXT, direct anatomical language is appropriate when the scene calls for it. If that anatomy is not established, DO NOT invent a body fact merely to satisfy a vocabulary quota. Deliver the requested directness through canon-safe named acts, physical action, sensation, dialogue, climax/resolution, and aftermath, and let the independent semantic verifier judge whether the request was fulfilled.
"""
    messages[0]["content"] = f"{messages[0]['content']}\n{contract}"
    return messages


def install_explicitness_enforcement() -> None:
    global _BASE_BUILD_MESSAGES, _BASE_STREAMED_COMPLETE
    _BASE_BUILD_MESSAGES = generation.build_messages
    generation.build_messages = build_messages
    refinement.explicit_delivery_failure = strict_explicit_delivery_failure

    if streaming_generation.generate_complete_prose_streamed is not generate_verified_studio_prose_streamed:
        _BASE_STREAMED_COMPLETE = streaming_generation.generate_complete_prose_streamed
        streaming_generation.generate_complete_prose_streamed = generate_verified_studio_prose_streamed

    # Global fallback order stays prose-first so a stale non-adult request never falls
    # through to the erotica specialist. Explicit adult routing is handled separately.
    model_provisioning.BASELINE_CREATIVE_MODEL = MAGNUM_V4_MODEL
    model_provisioning.ADULT_EXPLICIT_CREATIVE_MODEL = ADULT_EXPLICIT_SPECIALIST_MODEL
    ollama_runtime._RECOMMENDED_MODELS = (
        MAGNUM_V4_MODEL,
        PYGMALION_3_MODEL,
        FAST_MODEL,
        ADULT_EXPLICIT_SPECIALIST_MODEL,
        HIGH_HEAT_CYDONIA_MODEL,
        HERETIC_ROCINANTE_MODEL,
        "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m",
    )