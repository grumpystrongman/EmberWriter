from __future__ import annotations

import re

from . import generation_reliability as reliability
from . import streaming_generation as streaming
from .writing_model_catalog import adult_model_score as catalog_adult_model_score

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


def hard_quality_failure(text: str) -> str:
    if not text.strip():
        return "empty draft"

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
    """Use the shared capability catalog so refinement cannot restore stale rankings."""
    return catalog_adult_model_score(model)


_base_verify_studio_scene_delivery = reliability.verify_studio_scene_delivery


async def refined_verify_studio_scene_delivery(config, messages, draft: str) -> dict[str, object]:
    verdict = await _base_verify_studio_scene_delivery(config, messages, draft)
    prompt = reliability._author_instruction(messages)
    delivery_failure = explicit_delivery_failure(prompt, draft)
    if delivery_failure:
        verdict["verified"] = False
        verdict["requested_explicitness_delivered"] = False
        verdict["reason"] = delivery_failure
    return verdict


class RefinedNoveltyStreamFilter(reliability._original_novelty_filter):
    """Buffer the unfinished sentence so lexical collapse never becomes a saved live delta."""

    def __init__(self, emit, prior_text: str = "") -> None:
        super().__init__(emit, prior_text)
        self._discard_tail_from: int | None = None
        self._emit_pending = ""

    def _unfinished_sentence_start(self) -> int:
        boundaries = list(re.finditer(r"(?<=[.!?…])\s+", self._emit_pending))
        return boundaries[-1].end() if boundaries else 0

    def _safe_emit_boundary(self) -> int:
        sentence_boundaries = list(re.finditer(r"(?<=[.!?…])\s+", self._emit_pending))
        paragraph_boundaries = list(re.finditer(r"\n\s*\n", self._emit_pending))
        sentence_end = sentence_boundaries[-1].end() if sentence_boundaries else 0
        paragraph_end = paragraph_boundaries[-1].end() if paragraph_boundaries else 0
        return max(sentence_end, paragraph_end)

    @property
    def text(self) -> str:
        raw = self._raw
        if self._discard_tail_from is not None:
            raw = raw[: self._discard_tail_from]
        cleaned, _removed, _novelty = streaming.dedupe_repetitive_prose(raw, self._prior_text)
        return cleaned

    async def feed(self, piece: str) -> None:
        self._raw += piece
        self._scan_buffer += piece
        self._emit_pending += piece

        unfinished_start = self._unfinished_sentence_start()
        unfinished = self._emit_pending[unfinished_start:].strip()
        if looks_like_semantic_chain(unfinished):
            # Emit only complete prose that preceded the bad unfinished sentence. The pathological
            # tail is never forwarded to the Studio delta buffer, so it cannot become the final
            # partial if recovery later fails.
            safe_prefix = self._emit_pending[:unfinished_start]
            if safe_prefix:
                await self._emit(safe_prefix)
            self._discard_tail_from = len(self._raw) - len(self._emit_pending) + unfinished_start
            self._emit_pending = ""
            self.removed_units += 2
            raise streaming.RepetitionLoopDetected(
                "model entered a runaway semantic-chain degeneration loop"
            )

        safe_boundary = self._safe_emit_boundary()
        if safe_boundary:
            safe = self._emit_pending[:safe_boundary]
            self._emit_pending = self._emit_pending[safe_boundary:]
            if safe:
                await self._emit(safe)

        # Preserve the repository's proven paragraph-level repetition behavior exactly.
        while True:
            match = re.search(r"\n\s*\n", self._scan_buffer)
            if not match:
                break
            paragraph = self._scan_buffer[: match.start()].strip()
            self._scan_buffer = self._scan_buffer[match.end() :]
            if not paragraph:
                continue
            self.raw_words += reliability._word_count(paragraph)
            normalized = streaming._normalize_prose(paragraph)
            duplicate = (
                len(paragraph) >= streaming._REPEAT_PARAGRAPH_MIN_CHARS
                and any(
                    streaming._similar(normalized, previous)
                    >= streaming._REPEAT_PARAGRAPH_SIMILARITY
                    for previous in self._paragraph_memory[-streaming._REPEAT_RECENT_PARAGRAPHS :]
                )
            )
            if duplicate:
                self.removed_units += 1
                if self.removed_units >= 2:
                    raise streaming.RepetitionLoopDetected("model entered a paragraph repetition loop")
                continue
            if normalized:
                self._paragraph_memory.append(normalized)
                self._paragraph_memory = self._paragraph_memory[-streaming._REPEAT_RECENT_PARAGRAPHS :]

    async def finish(self) -> None:
        tail = self._scan_buffer.strip()
        if tail:
            self.raw_words += reliability._word_count(tail)
        self._scan_buffer = ""

        if self._discard_tail_from is None and self._emit_pending:
            pending = self._emit_pending
            self._emit_pending = ""
            await self._emit(pending)
        else:
            self._emit_pending = ""


def install_refinement() -> None:
    # The base reliability wrapper resolves these globals at call time, so replacing them here
    # also refines delivery verification, model routing, and ceiling-compression validation.
    reliability._hard_quality_failure = hard_quality_failure
    reliability.adult_model_score = refined_adult_model_score
    reliability.HardenedNoveltyStreamFilter = RefinedNoveltyStreamFilter
    streaming._NoveltyStreamFilter = RefinedNoveltyStreamFilter
    streaming.verify_studio_scene_delivery = refined_verify_studio_scene_delivery
