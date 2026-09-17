from __future__ import annotations

import re

from . import generation_reliability as reliability
from . import streaming_generation as streaming
from .prose_quality import diagnose_prose

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

    issues = diagnose_prose(text)
    chain = _long_chain_sentence(text)
    if chain:
        return (
            "Runaway syntax detected with semantic-chain degeneration: a punctuation-starved "
            f"association chain reached {len(_words(chain))} words."
        )

    # Phrase-level recycling is still a deterministic failure even when it is not a thesaurus chain.
    for issue in issues:
        if issue.startswith("Substantial phrase-level repetition"):
            return issue
    return ""


class RefinedNoveltyStreamFilter(reliability._original_novelty_filter):
    """Interrupt the observed lexical-collapse signature without banning long sentences."""

    def __init__(self, emit, prior_text: str = "") -> None:
        super().__init__(emit, prior_text)
        self._discard_tail_from: int | None = None

    def _current_sentence_text(self) -> str:
        paragraph = re.split(r"\n\s*\n", self._scan_buffer)[-1]
        return re.split(r"(?<=[.!?…])\s+", paragraph)[-1].strip()

    def _tail_start(self) -> int:
        matches = list(re.finditer(r"\n\s*\n", self._raw))
        return matches[-1].end() if matches else 0

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

        sentence = self._current_sentence_text()
        if looks_like_semantic_chain(sentence):
            self._discard_tail_from = self._tail_start()
            self.removed_units += 2
            raise streaming.RepetitionLoopDetected(
                "model entered a runaway semantic-chain degeneration loop"
            )

        await self._emit(piece)

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


def install_refinement() -> None:
    # The base reliability wrapper resolves this global at call time, so replacing it here
    # also refines delivery verification and ceiling-compression validation.
    reliability._hard_quality_failure = hard_quality_failure
    reliability.HardenedNoveltyStreamFilter = RefinedNoveltyStreamFilter
    streaming._NoveltyStreamFilter = RefinedNoveltyStreamFilter
