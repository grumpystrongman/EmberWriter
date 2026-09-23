from __future__ import annotations

import re

from . import generation_reliability as reliability
from . import streaming_generation as streaming
from .intimacy_continuity import hard_choreography_failure

# The bad production sample did not merely contain a long sentence. It collapsed into a
# punctuation-starved association/thesaurus chain: connection -> soul -> destiny -> growth ->
# transformation -> judgment -> belief -> legacy -> power -> desire -> consent -> alignment, etc.
# Synthetic tests and some deliberate literary styles can legitimately contain long sentences,
# so length alone must never be the trigger.
_SEMANTIC_CHAIN_TERMS = {
    "connection", "connected", "connect", "memory", "essence", "soul", "spirit",
    "destiny", "eternity", "eternal", "forever", "sacred", "foundation", "growth",
    "development", "evolution", "evolve", "progression", "advancement", "improvement",
    "enhancement", "transformation", "metamorphosis", "transmutation", "manifestation",
    "realization", "recognition", "appreciation", "valuation", "assessment", "evaluation",
    "judgment", "determination", "decision", "choice", "preference", "belief", "faith",
    "doctrine", "principle", "legacy", "inheritance", "tradition", "remembrance", "honor",
    "admiration", "success", "achievement", "triumph", "victory", "domination", "mastery",
    "authority", "power", "strength", "vitality", "capability", "potential", "possibility",
    "probability", "uncertainty", "ambiguity", "complexity", "clarity", "harmony", "unity",
    "integrity", "wholeness", "completeness", "richness", "intensity", "consequence",
    "aftermath", "destruction", "annihilation", "extinction", "discrimination", "prejudice",
    "bias", "attitude", "perspective", "desire", "longing", "yearning", "craving", "lust",
    "passion", "enthusiasm", "consent", "permission", "approval", "validation",
    "authorization", "alignment", "synchrony", "agreement", "bind", "unite", "couple",
    "reproduce", "expand", "increase", "intensify", "reinforce", "support", "preserve",
    "control", "regulate", "manage", "guide", "teach", "enlighten", "illumination",
    "discovery", "understanding", "knowledge", "wisdom", "truth", "reality", "awareness",
    "consciousness", "experience", "embodiment", "existence", "purpose", "meaning",
}

_EXPLICIT_REQUEST_PATTERNS = (
    r"\bexplicit\b",
    r"\bsex\s+scene\b",
    r"\bpenetrat(?:e|ion|ing)\b",
    r"\bgenital(?:s|ia)?\b",
    r"\bblow\s*job\b",
    r"\bhand\s*job\b",
    r"\banal\b",
    r"\bcumm?(?:ing)?\b",
    r"\borgasm\b",
)
_DIRECT_DRAFT_PATTERNS = (
    r"\b(?:penis|cock|dick)\b",
    r"\b(?:vagina|pussy|cunt|clit|clitoris)\b",
    r"\b(?:anus|asshole|genitals?|genitalia)\b",
    r"\bpenetrat(?:e|ed|es|ing|ion)\b",
    r"\b(?:fuck|fucked|fucking|thrust|thrusting|thrusts)\b",
    r"\b(?:blow\s*job|hand\s*job|oral\s+sex)\b",
    r"\b(?:suck|sucked|sucking|lick|licked|licking)\b",
    r"\b(?:masturbat\w*|stroke|stroked|stroking)\b",
    r"\b(?:semen|ejaculat\w*|cum|cumming)\b",
    r"\b(?:orgasm|orgasmed|climax|climaxed|came)\b",
)
_CLIMAX_PATTERN = re.compile(r"\b(?:orgasm(?:ed)?|climax(?:ed)?|came|cum|cumming|ejaculat\w*)\b", re.IGNORECASE)
_BOTH_CLIMAX_REQUEST = re.compile(
    r"\bboth\b.{0,60}\b(?:orgasm|climax|cum|come)",
    re.IGNORECASE | re.DOTALL,
)
_BOTH_CLIMAX_DRAFT = re.compile(
    r"\bboth\b.{0,70}\b(?:orgasm(?:ed)?|climax(?:ed)?|came|cum|cumming)",
    re.IGNORECASE | re.DOTALL,
)


_MISSIONARY_REQUEST = re.compile(r"\bmissionary\b", re.IGNORECASE)
_DOGGY_REQUEST = re.compile(r"\bdoggy(?:\s+style)?\b", re.IGNORECASE)
_BLOWJOB_REQUEST = re.compile(r"\bblow\s*job\b", re.IGNORECASE)
_ANAL_REQUEST = re.compile(r"\banal\b", re.IGNORECASE)
_NEGATED_REQUEST = re.compile(r"\b(?:no|not|avoid|without|exclude|skip)\b[^.!?\n]{0,24}$", re.IGNORECASE)

_MISSIONARY_GEOMETRY = re.compile(
    r"\b(?:on\s+(?:her|his|their)\s+back|lay\s+back|lying\s+on\s+(?:her|his|their)\s+back|"
    r"rolled?\s+onto\s+(?:her|his|their)\s+back)\b",
    re.IGNORECASE,
)
_MISSIONARY_PARTNER_FRONT = re.compile(
    r"\b(?:between\s+(?:her|his|their)\s+legs|facing\s+(?:her|him|them)|"
    r"over\s+(?:her|him|them)|legs?\s+(?:raised|apart|around))\b",
    re.IGNORECASE,
)
_DOGGY_GEOMETRY = re.compile(
    r"\b(?:hands?\s+and\s+knees?|all\s+fours|facing\s+away|from\s+behind|"
    r"kneeling\s+behind|chest[-\s]down[^.!?\n]{0,80}hips?\s+raised)\b",
    re.IGNORECASE,
)
_BLOWJOB_DELIVERY = re.compile(
    r"\b(?:mouth|lips|suck\w*|oral\s+sex|blow\s*job)\b[^.!?\n]{0,120}\b(?:penis|cock|dick)\b|"
    r"\b(?:penis|cock|dick)\b[^.!?\n]{0,120}\b(?:mouth|lips|suck\w*|oral\s+sex|blow\s*job)\b",
    re.IGNORECASE,
)
_ANAL_TARGET = re.compile(r"\b(?:anus|anal\s+opening|asshole)\b", re.IGNORECASE)
_POSITION_PENETRATION = re.compile(
    r"\b(?:penetrat\w*|thrust\w*|fuck\w*|enter(?:ed|ing)?|push(?:ed|ing)?\s+into)\b",
    re.IGNORECASE,
)


def _positively_requested(prompt: str, pattern: re.Pattern[str]) -> bool:
    for match in pattern.finditer(prompt):
        prefix = prompt[max(0, match.start() - 32):match.start()]
        if not _NEGATED_REQUEST.search(prefix):
            return True
    return False


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


def _beat_windows(draft: str) -> list[str]:
    paragraphs = _paragraphs(draft)
    windows = list(paragraphs)
    windows.extend(
        f"{paragraphs[index]}\n\n{paragraphs[index + 1]}"
        for index in range(len(paragraphs) - 1)
    )
    return windows


def _same_beat(draft: str, *patterns: re.Pattern[str]) -> bool:
    return any(all(pattern.search(window) for pattern in patterns) for window in _beat_windows(draft))


def requested_act_delivery_failure(prompt: str, draft: str) -> str:
    """Require named acts/positions to occur as recognizable, same-beat physical geometry."""
    if _positively_requested(prompt, _MISSIONARY_REQUEST) and not _same_beat(
        draft,
        _MISSIONARY_GEOMETRY,
        _MISSIONARY_PARTNER_FRONT,
        _POSITION_PENETRATION,
    ):
        return (
            "author requested missionary/face-to-face sex, but no local beat window establishes "
            "receiver-on-back + partner-in-front/between-legs + penetrative action"
        )
    if _positively_requested(prompt, _DOGGY_REQUEST) and not _same_beat(
        draft,
        _DOGGY_GEOMETRY,
        _POSITION_PENETRATION,
    ):
        return (
            "author requested doggy/rear sex, but no local beat window establishes "
            "receiver-facing-away/hips-accessible + partner-behind + penetrative action"
        )
    if _positively_requested(prompt, _BLOWJOB_REQUEST) and not _BLOWJOB_DELIVERY.search(draft):
        return "author requested a blowjob/oral-on-penis beat, but no clear oral-to-penis action occurs"
    if _positively_requested(prompt, _ANAL_REQUEST) and not _same_beat(
        draft,
        _ANAL_TARGET,
        _POSITION_PENETRATION,
    ):
        return (
            "author requested anal sex, but no local beat window identifies anal receiving anatomy "
            "together with penetrative action"
        )
    return ""


_ANATOMY_CANON_GROUPS = {
    "penis": ("penis", "cock", "dick"),
    "vagina": ("vagina", "vaginal"),
    "vulva": ("vulva", "pussy", "cunt"),
    "clitoris": ("clit", "clitoris"),
    "anus": ("anus", "anal", "asshole"),
    "breasts": ("breast", "breasts", "tits"),
}

_VAGINAL_TEMPLATE_EUPHEMISM = re.compile(
    r"\b(?:slick|wet)\s+entrance\b|"
    r"\b(?:her|his|their|the|[A-Za-z][A-Za-z'’-]{1,30}['’]s)\s+folds\b|"
    r"\b(?:vaginal\s+)?inner\s+walls\b",
    re.IGNORECASE,
)


def _character_context_sections(context: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^###\s+([^\n]+)\s*$", context))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(context)
        name = match.group(1).strip()
        body = context[match.end():end]
        sections.append((name, body))
    return sections


def _body_canon_sets(section: str) -> tuple[set[str], set[str]]:
    present: set[str] = set()
    absent: set[str] = set()

    absent_phrases = re.findall(
        r"(?i)\b(?:does\s+not\s+have|doesn't\s+have|has\s+no|without)\s+([^.;\n]+)",
        section,
    )
    present_phrases = re.findall(
        r"(?i)\bhas\s+(?!no\b)([^.;\n]+)",
        section,
    )
    label_phrases = re.findall(
        r"(?im)^\s*(?:[-*]\s*)?(?:genitals?|intimate\s+anatomy|anatomy)\s*:\s*([^\n]+)",
        section,
    )

    for group, terms in _ANATOMY_CANON_GROUPS.items():
        term_pattern = re.compile(r"\b(?:" + "|".join(re.escape(term) for term in terms) + r")\b", re.IGNORECASE)
        if any(term_pattern.search(phrase) for phrase in absent_phrases):
            absent.add(group)
        if any(term_pattern.search(phrase) for phrase in [*present_phrases, *label_phrases]):
            present.add(group)
    return present, absent


def hard_body_canon_failure(context: str, draft: str) -> str:
    """Reject direct contradictions to anatomy the author explicitly marked present/absent."""
    sections = _character_context_sections(context)
    if not sections:
        return ""

    parsed: dict[str, tuple[set[str], set[str]]] = {}
    for name, section in sections:
        present, absent = _body_canon_sets(section)
        if present or absent:
            parsed[name] = (present, absent)
    if not parsed:
        return ""

    explicitly_present_receptive = set().union(
        *(present & {"vagina", "vulva", "clitoris"} for present, _absent in parsed.values())
    )
    explicitly_absent_receptive = set().union(
        *(absent & {"vagina", "vulva", "clitoris"} for _present, absent in parsed.values())
    )
    if (
        explicitly_absent_receptive
        and not explicitly_present_receptive
        and _VAGINAL_TEMPLATE_EUPHEMISM.search(draft)
    ):
        return (
            "hard body-canon conflict: draft uses vague cis-female-template receptive anatomy "
            "even though no participant has that anatomy established in canon"
        )

    for name, (_present, absent) in parsed.items():
        for group in absent:
            terms = _ANATOMY_CANON_GROUPS[group]
            term_pattern = r"(?:" + "|".join(re.escape(term) for term in terms) + r")"
            if not re.search(rf"\b{term_pattern}\b", draft, flags=re.IGNORECASE):
                continue

            name_pattern = re.escape(name)
            direct_assignment = re.search(
                rf"(?i)(?:\b{name_pattern}(?:['’]s)?\b[^.!?\n]{{0,90}}\b{term_pattern}\b|"
                rf"\b{term_pattern}\b[^.!?\n]{{0,90}}\b{name_pattern}\b)",
                draft,
            )
            other_has_group = any(
                group in present
                for other_name, (present, _other_absent) in parsed.items()
                if other_name != name
            )
            if direct_assignment or not other_has_group:
                return (
                    f"hard body-canon conflict: {name} is explicitly established as not having {group} anatomy, "
                    "but the draft assigns or uses that anatomy in the scene"
                )
    return ""


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text.casefold())


def looks_like_semantic_chain(text: str) -> bool:
    words = _words(text)
    if len(words) < 110:
        return False

    # Require very sparse terminal punctuation. The production failure was hundreds of words
    # without a natural sentence boundary; this prevents ordinary multi-sentence abstract prose
    # from being classified as degeneration.
    terminals = len(re.findall(r"[.!?…]", text))
    if terminals > 2:
        return False

    hits = {word for word in words if word in _SEMANTIC_CHAIN_TERMS}
    hit_count = sum(1 for word in words if word in _SEMANTIC_CHAIN_TERMS)
    # Require both breadth and density. A normal paragraph can mention 'desire', 'choice', and
    # 'connection'; a collapse walks through many unrelated abstractions in rapid succession.
    return len(hits) >= 12 and hit_count >= max(14, int(len(words) * 0.10))


def _long_chain_sentence(text: str) -> str:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?…])\s+", text) if part.strip()]
    for sentence in sentences:
        if looks_like_semantic_chain(sentence):
            return sentence
    if looks_like_semantic_chain(text):
        return text
    return ""


_RUNAWAY_REPEATED_WORD = re.compile(
    r"\b([A-Za-z][A-Za-z'’-]{2,})\b(?:\s*,?\s*\1\b){2,}",
    re.IGNORECASE,
)


def _duplicate_short_sentence_failure(text: str) -> str:
    counts: dict[str, int] = {}
    for sentence in re.split(r"(?<=[.!?…])\s+|\n+", text):
        normalized = " ".join(_words(sentence))
        if len(normalized) < 20 or len(normalized.split()) < 4:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
    repeated = [
        (sentence, count)
        for sentence, count in counts.items()
        if count >= 2
    ]
    if len(repeated) >= 2 or any(count >= 3 for count in counts.values()):
        examples = "; ".join(
            f"{count}x '{sentence[:72]}{'…' if len(sentence) > 72 else ''}'"
            for sentence, count in sorted(repeated, key=lambda item: (-item[1], item[0]))[:3]
        )
        return (
            "multiple short sentences are being recycled verbatim instead of advancing the scene"
            + (f" (examples: {examples})" if examples else "")
        )
    return ""


def hard_quality_failure(text: str) -> str:
    if not text.strip():
        return "empty draft"

    repeated_word = _RUNAWAY_REPEATED_WORD.search(text)
    if repeated_word:
        return f"runaway repeated word detected: {repeated_word.group(1)}"

    duplicate_sentence = _duplicate_short_sentence_failure(text)
    if duplicate_sentence:
        return duplicate_sentence

    chain = _long_chain_sentence(text)
    if chain:
        return (
            "Runaway syntax detected with semantic-chain degeneration: a punctuation-starved "
            f"association chain reached {len(_words(chain))} words."
        )

    # Paragraph/phrase repetition already has its own streaming guard and the independent scene
    # verifier also reports repetition. Keeping it out of this second deterministic gate prevents
    # normalized test tokens (draft0, draft1, ...) and deliberate refrains from becoming false fails.
    return ""


def requires_direct_explicitness(prompt: str) -> bool:
    lowered = prompt.casefold()
    hits = sum(bool(re.search(pattern, lowered, flags=re.IGNORECASE)) for pattern in _EXPLICIT_REQUEST_PATTERNS)
    return hits >= 2 or bool(re.search(r"\bexplicit\b", lowered))


def direct_explicitness_score(draft: str) -> int:
    return sum(
        bool(re.search(pattern, draft, flags=re.IGNORECASE))
        for pattern in _DIRECT_DRAFT_PATTERNS
    )


def explicit_delivery_failure(prompt: str, draft: str) -> str:
    if not requires_direct_explicitness(prompt):
        return ""
    score = direct_explicitness_score(draft)
    if score < 3:
        return (
            "author requested direct explicit scene delivery, but the draft lacks enough direct "
            "anatomical/sexual-action evidence and appears euphemistic or faded"
        )
    if not _CLIMAX_PATTERN.search(draft):
        return "author requested explicit completion, but the draft has no clear climax evidence"
    if _BOTH_CLIMAX_REQUEST.search(prompt):
        climax_mentions = len(_CLIMAX_PATTERN.findall(draft))
        if not _BOTH_CLIMAX_DRAFT.search(draft) and climax_mentions < 2:
            return "author required both participants to climax, but the draft does not support both"
    return ""


def refined_adult_model_score(model: str) -> int:
    """Prefer adult-capable creative/RP models, not merely uncensored instruct models."""
    name = model.casefold()
    if "cydonia" in name and any(token in name for token in ("heretic", "abliter", "decensor")):
        return 280
    if "rocinante-x" in name:
        return 270
    if "rocinante" in name:
        return 260
    if any(token in name for token in ("magidonia", "magnum", "mag-mell", "mag_mell")):
        return 245
    # Standard Cydonia remains a strong prose model, but current non-decensored variants can
    # refuse high-heat requests, so it ranks below a dedicated Rocinante-family option.
    if "cydonia" in name:
        return 235
    if any(token in name for token in ("stheno", "pygmalion", "lunaris", "nemomix")):
        return 220
    if "qwen2.5-14b" in name and "heretic" in name:
        return 150
    if "qwen3-8b" in name and "heretic" in name:
        return 140
    if any(token in name for token in ("heretic", "uncensored", "abliterat")):
        return 120
    return 0


_base_verify_studio_scene_delivery = reliability.verify_studio_scene_delivery


async def refined_verify_studio_scene_delivery(config, messages, draft: str) -> dict[str, object]:
    request_context = streaming._verifier_source_context(messages)
    body_failure = hard_body_canon_failure(request_context, draft)
    if body_failure:
        return {
            "verified": False,
            "canon_respected": False,
            "physical_continuity": True,
            "reason": body_failure,
        }

    choreography_failure = hard_choreography_failure(draft)
    if choreography_failure:
        return {
            "verified": False,
            "canon_respected": True,
            "physical_continuity": False,
            "reason": choreography_failure,
        }

    verdict = await _base_verify_studio_scene_delivery(config, messages, draft)
    prompt = reliability._author_instruction(messages)
    delivery_failure = explicit_delivery_failure(prompt, draft)
    if delivery_failure:
        verdict["verified"] = False
        verdict["requested_explicitness_delivered"] = False
        verdict["reason"] = delivery_failure
        return verdict

    act_failure = requested_act_delivery_failure(prompt, draft)
    if act_failure:
        verdict["verified"] = False
        verdict["requested_explicitness_delivered"] = False
        verdict["physical_continuity"] = False
        verdict["reason"] = act_failure
    return verdict


class RefinedNoveltyStreamFilter(reliability._original_novelty_filter):
    """Reject semantic-chain collapse before any rejected paragraph reaches Studio."""

    def __init__(self, emit, prior_text: str = "") -> None:
        super().__init__(emit, prior_text)
        self._semantic_chain_rejected = False

    def _unfinished_sentence(self, candidate: str) -> str:
        sentence_boundaries = list(re.finditer(r"(?<=[.!?…])\s+", candidate))
        start = sentence_boundaries[-1].end() if sentence_boundaries else 0
        return candidate[start:].strip()

    async def feed(self, piece: str) -> None:
        # Inspect the still-uncommitted paragraph before the transactional base filter
        # is allowed to accept or emit it. This preserves live paragraph streaming while
        # guaranteeing a rejected semantic chain never becomes author-visible prose.
        candidate = f"{self._scan_buffer}{piece}"
        unfinished = self._unfinished_sentence(candidate)
        if looks_like_semantic_chain(unfinished):
            self._raw += piece
            self._semantic_chain_rejected = True
            self.removed_units += 2
            raise streaming.RepetitionLoopDetected(
                "model entered a runaway semantic-chain degeneration loop"
            )
        await super().feed(piece)

    async def finish(self) -> None:
        if self._semantic_chain_rejected:
            # The current uncommitted paragraph is the rejected chain. Never resurrect it.
            self._scan_buffer = ""
            return
        # The base filter validates and emits the final paragraph transactionally.
        await super().finish()


def install_refinement() -> None:
    # The base reliability wrapper resolves these globals at call time, so replacing them here
    # also refines delivery verification, model routing, and ceiling-compression validation.
    reliability._hard_quality_failure = hard_quality_failure
    reliability.adult_model_score = refined_adult_model_score
    reliability.HardenedNoveltyStreamFilter = RefinedNoveltyStreamFilter
    streaming._NoveltyStreamFilter = RefinedNoveltyStreamFilter
    streaming.verify_studio_scene_delivery = refined_verify_studio_scene_delivery
