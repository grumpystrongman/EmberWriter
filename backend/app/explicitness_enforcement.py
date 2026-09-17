from __future__ import annotations

import re
from dataclasses import dataclass

from . import generation
from . import generation_reliability_refinement as refinement
from . import model_provisioning
from . import ollama_runtime

HERETIC_ROCINANTE_MODEL = (
    "hf.co/mradermacher/Rocinante-X-12B-v1-Heretic-Uncensored-GGUF:Q4_K_M"
)
HIGH_HEAT_CYDONIA_MODEL = "Fermi/Cydonia-24B-v4.3-heretic-vision:Q4_K_M"


@dataclass(frozen=True)
class ExplicitnessProfile:
    anatomy_groups: int
    action_groups: int
    direct_action_sentences: int
    explicit_sentences: int
    climax_mentions: int
    fluid_mentions: int


_ANATOMY_GROUPS = (
    re.compile(r"\b(?:penis|cock|dick)\b", re.IGNORECASE),
    re.compile(r"\b(?:vagina|vaginal|vulva|pussy|cunt|clit|clitoris)\b", re.IGNORECASE),
    re.compile(r"\b(?:anus|anal|asshole)\b", re.IGNORECASE),
    re.compile(r"\b(?:breasts?|tits?|nipples?)\b", re.IGNORECASE),
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
    r"\b(?:penis|cock|dick|vagina|vaginal|vulva|pussy|cunt|clit|clitoris|anus|anal|asshole|"
    r"penetrat\w*|fuck\w*|thrust\w*|blow\s*job|hand\s*job|oral\s+sex|suck\w*|lick\w*|"
    r"masturbat\w*|stroke\w*|semen|ejaculat\w*|cum|cumming|orgasm\w*)\b",
    re.IGNORECASE,
)
_EUPHEMISM_HEAVY = re.compile(
    r"\b(?:breached|joined|merged|union|center|length|release|completion|consummation|"
    r"bodies\s+moving|skin\s+met\s+skin|became\s+one)\b",
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

_BASE_BUILD_MESSAGES = generation.build_messages


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?…])\s+|\n+", text) if part.strip()]


def explicitness_profile(draft: str) -> ExplicitnessProfile:
    sentences = _sentences(draft)
    anatomy_groups = sum(bool(pattern.search(draft)) for pattern in _ANATOMY_GROUPS)
    action_groups = sum(bool(pattern.search(draft)) for pattern in _ACTION_GROUPS)
    explicit_sentences = sum(bool(_EXPLICIT_TOKEN.search(sentence)) for sentence in sentences)
    direct_action_sentences = 0
    for sentence in sentences:
        anatomy = any(pattern.search(sentence) for pattern in _ANATOMY_GROUPS)
        action = any(pattern.search(sentence) for pattern in _ACTION_GROUPS)
        named_act = bool(re.search(r"\b(?:blow\s*job|hand\s*job|oral\s+sex|anal\s+sex)\b", sentence, re.IGNORECASE))
        if (anatomy and action) or named_act:
            direct_action_sentences += 1
    return ExplicitnessProfile(
        anatomy_groups=anatomy_groups,
        action_groups=action_groups,
        direct_action_sentences=direct_action_sentences,
        explicit_sentences=explicit_sentences,
        climax_mentions=len(_CLIMAX.findall(draft)),
        fluid_mentions=len(_FLUID.findall(draft)),
    )


def strict_explicit_delivery_failure(prompt: str, draft: str) -> str:
    if not refinement.requires_direct_explicitness(prompt):
        return ""

    profile = explicitness_profile(draft)
    if profile.anatomy_groups < 2:
        return (
            "author requested explicit on-page sexual detail, but the draft names too little concrete anatomy; "
            "this is either model softening or missing intimate-body canon and must not be accepted as explicit"
        )
    if profile.action_groups < 2:
        return "author requested explicit sexual action, but the draft does not contain enough distinct direct action types"
    if profile.direct_action_sentences < 3 or profile.explicit_sentences < 5:
        return (
            "author requested sustained explicit detail, but direct anatomy/action language is too sparse and the scene "
            "reads as euphemistic or PG-13"
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
- Directness must be sustained across the encounter, not satisfied by one token or one sentence. Several separate sentences should plainly describe concrete anatomy and concrete sexual actions.
- Keep the prose character-specific and readable; direct vocabulary is not permission for repetitive choreography or a body-part inventory.
- Intimate anatomy remains hard canon. If a character's relevant anatomy is explicitly established in AUTHOR INSTRUCTION or PROJECT CONTEXT, name it directly when the scene calls for it. If the requested level of anatomical specificity cannot be delivered without inventing a body fact, do not silently soften the whole scene; preserve all other direct detail and make the missing-canon limitation explicit to the delivery verifier.
"""
    messages[0]["content"] = f"{messages[0]['content']}\n{contract}"
    return messages


def install_explicitness_enforcement() -> None:
    global _BASE_BUILD_MESSAGES
    _BASE_BUILD_MESSAGES = generation.build_messages
    generation.build_messages = build_messages
    refinement.explicit_delivery_failure = strict_explicit_delivery_failure

    # Keep installation, background provisioning, and stale-model repair on one managed model
    # contract. This runs after the reliability layer, which otherwise restores the old Qwen /
    # standard-Rocinante recommendation list.
    model_provisioning.BASELINE_CREATIVE_MODEL = HERETIC_ROCINANTE_MODEL
    ollama_runtime._RECOMMENDED_MODELS = (
        HIGH_HEAT_CYDONIA_MODEL,
        HERETIC_ROCINANTE_MODEL,
        "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m",
        "R4C3R/qwen3-8b-heretic:q4_k_m",
    )