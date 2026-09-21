from __future__ import annotations

import re
from dataclasses import dataclass

from . import generation as generation
from . import ollama_runtime
from .model_catalog import (
    ADULT_EXPLICIT_FAMILY,
    ADULT_EXPLICIT_MODEL,
    CHARACTER_MODEL,
    FAST_MODEL,
    GENERAL_PROSE_MODEL,
)
from . import streaming_generation as streaming
from .models import ProviderConfig
from .prose_quality import diagnose_prose


@dataclass(frozen=True)
class SceneLengthContract:
    floor_words: int | None = None
    target_words: int | None = None
    max_words: int | None = None


_UPPER_LIMIT_PATTERNS = (
    r"\bunder\s+(\d{2,5})\s*words?\b",
    r"\bless\s+than\s+(\d{2,5})\s*words?\b",
    r"\bfewer\s+than\s+(\d{2,5})\s*words?\b",
    r"\bno\s+more\s+than\s+(\d{2,5})\s*words?\b",
    r"\bat\s+most\s+(\d{2,5})\s*words?\b",
    r"\b(?:max|max(?:imum)?(?:\s+of)?|capped\s+at)\s*[:=]?\s*(\d{2,5})\s*words?\b",
)
_RANGE_PATTERN = re.compile(r"\b(\d{2,5})\s*(?:-|–|—|to)\s*(\d{2,5})\s*words?\b", re.IGNORECASE)
_EXACT_PATTERN = re.compile(r"\b(?:exactly|about|around|roughly|approximately)\s+(\d{2,5})\s*words?\b", re.IGNORECASE)
_GENERIC_WORD_PATTERN = re.compile(r"\b(\d{3,5})\s*words?\b", re.IGNORECASE)

# Known creative/RP families are intentionally ranked above generic uncensored instruct models
# for adult manuscript prose. Exact model names are not required; local variants still benefit.
def adult_model_score(model: str) -> int:
    name = model.casefold()
    score = 0
    if ADULT_EXPLICIT_FAMILY in name:
        score = 1000
    elif "cydonia" in name and ("heretic" in name or "abliter" in name or "decensor" in name):
        score = 260
    elif "rocinante-x" in name:
        score = 250
    elif "cydonia" in name:
        score = 240
    elif "rocinante" in name:
        score = 230
    elif any(token in name for token in ("magidonia", "magnum", "mag-mell", "mag_mell")):
        score = 220
    elif any(token in name for token in ("stheno", "pygmalion", "lunaris", "nemomix")):
        score = 205
    elif "qwen2.5-14b" in name and "heretic" in name:
        score = 150
    elif "qwen3-8b" in name and "heretic" in name:
        score = 140
    elif any(token in name for token in ("heretic", "uncensored", "abliterat")):
        score = 120
    return score


def parse_scene_length(prompt: str, heat_level: str | None = None) -> SceneLengthContract:
    normalized = prompt.casefold()

    for pattern in _UPPER_LIMIT_PATTERNS:
        match = re.search(pattern, normalized, flags=re.IGNORECASE)
        if match:
            maximum = max(300, min(int(match.group(1)), 12000))
            # An author ceiling is not a minimum. Aim comfortably below it so the model has
            # room to land the ending without a forced continuation or a late truncation.
            floor = max(300, min(maximum - 100, int(maximum * 0.55)))
            target = max(floor, min(maximum - 75, int(maximum * 0.82)))
            return SceneLengthContract(floor_words=floor, target_words=target, max_words=maximum)

    ranged = _RANGE_PATTERN.search(normalized)
    if ranged:
        low, high = sorted((int(ranged.group(1)), int(ranged.group(2))))
        low = max(300, min(low, 12000))
        high = max(low, min(high, 12000))
        target = low + max(0, (high - low) // 2)
        return SceneLengthContract(floor_words=low, target_words=target, max_words=high)

    exact = _EXACT_PATTERN.search(normalized)
    if exact:
        target = max(300, min(int(exact.group(1)), 12000))
        return SceneLengthContract(floor_words=max(300, int(target * 0.8)), target_words=target)

    generic = _GENERIC_WORD_PATTERN.search(normalized)
    if generic:
        target = max(300, min(int(generic.group(1)), 12000))
        return SceneLengthContract(floor_words=target, target_words=target)

    if re.search(r"\b(?:brief|short|quick)\s+(?:scene|passage)\b", normalized):
        return SceneLengthContract(floor_words=700, target_words=850)

    defaults = {
        "simmer": 1000,
        "hot": 1200,
        "scorching": 1400,
        "inferno": 1600,
    }
    floor = defaults.get(heat_level or "", 1200)
    return SceneLengthContract(floor_words=floor, target_words=floor)


def _author_instruction(messages: list[dict[str, str]]) -> str:
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        marker = "AUTHOR INSTRUCTION\n"
        if marker not in content:
            continue
        instruction = content.split(marker, 1)[1]
        if "\n\nPROJECT CONTEXT\n" in instruction:
            instruction = instruction.split("\n\nPROJECT CONTEXT\n", 1)[0]
        return instruction.strip()
    return ""


def _length_contract_from_messages(messages: list[dict[str, str]]) -> SceneLengthContract:
    prompt = _author_instruction(messages)
    if not prompt:
        return SceneLengthContract()
    heat = None
    for message in messages:
        if message.get("role") != "system":
            continue
        match = re.search(r"Requested heat:\s*([a-z_]+)", message.get("content", ""), flags=re.IGNORECASE)
        if match:
            heat = match.group(1).casefold()
            break
    return parse_scene_length(prompt, heat)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:['’-]\w+)?\b", text))


def _assistant_words(messages: list[dict[str, str]]) -> int:
    # Continuation calls include the accepted draft as an assistant message. The original
    # two-message request does not, so this gives us a useful remaining word budget.
    return sum(_word_count(message.get("content", "")) for message in messages if message.get("role") == "assistant")


def _is_intimacy_request(messages: list[dict[str, str]]) -> bool:
    return any(
        message.get("role") == "system" and "Scene intent: intimacy" in message.get("content", "")
        for message in messages
    )


def _is_explicit_intimacy_request(messages: list[dict[str, str]]) -> bool:
    if not _is_intimacy_request(messages):
        return False
    system = "\n".join(
        message.get("content", "")
        for message in messages
        if message.get("role") == "system"
    ).casefold()
    if "adult-fiction scene specialist" in system:
        return True
    if "requested heat: scorching" in system or "requested heat: inferno" in system:
        return True
    prompt = _author_instruction(messages)
    return bool(
        re.search(
            r"\b(?:sex|sexual|erotic|explicit|penetrat\w*|oral\s+sex|blow\s*job|"
            r"hand\s*job|orgasm\w*|fuck\w*|cumm?\w*)\b",
            prompt,
            flags=re.IGNORECASE,
        )
    )


def _remaining_output_tokens(
    messages: list[dict[str, str]],
    requested_tokens: int | None,
) -> int | None:
    contract = _length_contract_from_messages(messages)
    if contract.max_words is None:
        return requested_tokens
    remaining_words = max(160, contract.max_words - _assistant_words(messages))
    # Creative prose typically consumes more than one token per English word. Cap each pass
    # against the remaining author budget so a continuation cannot blindly add another full scene.
    budget = max(256, int(remaining_words * 1.38))
    return min(requested_tokens, budget) if requested_tokens is not None else budget


async def _route_adult_model(config: ProviderConfig, messages: list[dict[str, str]]) -> None:
    if config.provider != "ollama" or not _is_intimacy_request(messages):
        return
    installed = await ollama_runtime.installed_ollama_models(config.base_url)
    if not installed:
        return

    by_name = {item.casefold(): item for item in installed}
    if _is_explicit_intimacy_request(messages):
        specialist = by_name.get(ADULT_EXPLICIT_MODEL.casefold())
        if specialist:
            config.model = specialist
            return

    ranked = sorted(installed, key=adult_model_score, reverse=True)
    best = ranked[0]
    if adult_model_score(best) <= 0:
        return
    current_score = adult_model_score(config.model)
    if current_score < adult_model_score(best):
        config.model = best


def _sampling_for_model(model: str, temperature: float, top_p: float) -> tuple[float, float, float]:
    name = model.casefold()
    # Only replace the generic prose defaults. Explicit caller choices (verification/editorial
    # passes) remain authoritative.
    if temperature != 0.9 or top_p != 0.95:
        repeat_penalty = 1.10 if "rocinante" in name else 1.08 if "cydonia" in name else 1.18
        return temperature, top_p, repeat_penalty
    if ADULT_EXPLICIT_FAMILY in name:
        return 0.80, 0.90, 1.05
    if "cydonia" in name:
        return 0.72, 0.90, 1.05
    if "rocinante" in name:
        return 0.80, 0.92, 1.10
    if "qwen" in name and "heretic" in name:
        return 0.78, 0.90, 1.15
    return temperature, top_p, 1.18


def _hard_quality_failure(text: str) -> str:
    if not text.strip():
        return "empty draft"
    issues = diagnose_prose(text)
    for issue in issues:
        if issue.startswith("Runaway syntax detected"):
            return issue
        if issue.startswith("Substantial phrase-level repetition"):
            return issue
        if issue.startswith("Abstract romantic significance is crowding out scene action"):
            return issue
    return ""


def _strip_markers(text: str) -> str:
    return text.replace(generation.SCENE_COMPLETE_MARKER, "").replace(generation.SCENE_CONTINUE_MARKER, "").strip()


# Keep references before installing wrappers.
_original_scene_word_floor = generation.scene_word_floor
_original_build_messages = generation.build_messages
_original_generate = generation.generate
_original_generate_complete = generation.generate_complete_prose
_original_generate_streamed = streaming.generate_streamed
_original_generate_complete_streamed = streaming.generate_complete_prose_streamed
_original_verify_delivery = streaming.verify_studio_scene_delivery
_original_novelty_filter = streaming._NoveltyStreamFilter


def scene_word_floor(prompt: str, heat_level: str | None = None) -> int:
    contract = parse_scene_length(prompt, heat_level)
    if contract.floor_words is not None:
        return contract.floor_words
    return _original_scene_word_floor(prompt, heat_level)


def build_messages(*args, **kwargs):
    messages = _original_build_messages(*args, **kwargs)
    prompt = args[1] if len(args) >= 2 else kwargs.get("prompt", "")
    heat_level = kwargs.get("heat_level")
    contract = parse_scene_length(str(prompt), heat_level)
    if contract.max_words is None:
        return messages

    target = contract.target_words or max(300, int(contract.max_words * 0.8))
    ceiling_note = f"""
Author word-limit contract (higher priority than generic heat-length defaults):
- HARD CEILING: the complete visible manuscript must be under {contract.max_words} words.
- Aim to finish around {target} words so the ending and immediate aftermath fit naturally before the ceiling.
- The anti-fragment floor is not permission to exceed the author's ceiling.
- Do not start a new setup, exposition detour, or repeated escalation merely to add length.
- If the requested event has landed, conclude cleanly rather than triggering another continuation pass.
"""
    messages[0]["content"] = f"{messages[0]['content']}\n{ceiling_note}"
    return messages


async def generate(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    temperature: float = 0.9,
    top_p: float = 0.95,
    json_mode: bool = False,
    max_output_tokens: int | None = None,
) -> str:
    await _route_adult_model(config, messages)
    temperature, top_p, _ = _sampling_for_model(config.model, temperature, top_p)
    max_output_tokens = _remaining_output_tokens(messages, max_output_tokens)
    return await _original_generate(
        config,
        messages,
        temperature=temperature,
        top_p=top_p,
        json_mode=json_mode,
        max_output_tokens=max_output_tokens,
    )


async def generate_streamed(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    on_delta,
    temperature: float = 0.9,
    top_p: float = 0.95,
    json_mode: bool = False,
    max_output_tokens: int | None = None,
) -> str:
    await _route_adult_model(config, messages)
    temperature, top_p, repeat_penalty = _sampling_for_model(config.model, temperature, top_p)
    max_output_tokens = _remaining_output_tokens(messages, max_output_tokens)

    old_penalty = streaming._OLLAMA_REPEAT_PENALTY
    try:
        if config.provider == "ollama" and _is_intimacy_request(messages):
            streaming._OLLAMA_REPEAT_PENALTY = repeat_penalty
        return await _original_generate_streamed(
            config,
            messages,
            on_delta=on_delta,
            temperature=temperature,
            top_p=top_p,
            json_mode=json_mode,
            max_output_tokens=max_output_tokens,
        )
    finally:
        streaming._OLLAMA_REPEAT_PENALTY = old_penalty


class HardenedNoveltyStreamFilter(_original_novelty_filter):
    """Stop a one-sentence lexical collapse before it can consume the whole scene."""

    def __init__(self, emit, prior_text: str = "") -> None:
        super().__init__(emit, prior_text)
        self._discard_tail_from: int | None = None

    def _current_sentence_words(self) -> int:
        paragraph = re.split(r"\n\s*\n", self._scan_buffer)[-1]
        sentence = re.split(r"(?<=[.!?…])\s+", paragraph)[-1]
        return _word_count(sentence)

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

        # The observed failure mode was a giant punctuation-free synonym/association chain.
        # At 120 words in one unfinished sentence, discard the whole current paragraph and
        # let the existing continuation recovery advance to a fresh beat.
        if self._current_sentence_words() >= 120:
            self._discard_tail_from = self._tail_start()
            self.removed_units += 2
            raise streaming.RepetitionLoopDetected("model entered a runaway single-sentence degeneration loop")

        await self._emit(piece)

        while True:
            match = re.search(r"\n\s*\n", self._scan_buffer)
            if not match:
                break
            paragraph = self._scan_buffer[: match.start()].strip()
            self._scan_buffer = self._scan_buffer[match.end() :]
            if not paragraph:
                continue
            self.raw_words += _word_count(paragraph)
            normalized = streaming._normalize_prose(paragraph)
            duplicate = (
                len(paragraph) >= streaming._REPEAT_PARAGRAPH_MIN_CHARS
                and any(
                    streaming._similar(normalized, previous) >= streaming._REPEAT_PARAGRAPH_SIMILARITY
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


async def verify_studio_scene_delivery(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    draft: str,
) -> dict[str, object]:
    verdict = await _original_verify_delivery(config, messages, draft)
    quality_failure = _hard_quality_failure(draft)
    if quality_failure:
        verdict["verified"] = False
        verdict["repetition_loop"] = True
        verdict["reason"] = f"deterministic prose gate rejected draft: {quality_failure[:220]}"
    return verdict


async def _compress_to_author_ceiling(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    draft: str,
    maximum: int,
) -> str:
    if _word_count(draft) <= maximum:
        return draft

    target = max(300, int(maximum * 0.84))
    author_prompt = _author_instruction(messages)
    edit_messages = [
        {
            "role": "system",
            "content": (
                "You are EmberWriter's manuscript compression editor. Scene intent: intimacy. "
                "Return only revised manuscript prose. Preserve the same participants, POV, consent, requested intensity, "
                "core events, climax/resolution requirements, continuity facts, and immediate aftermath. Remove setup drift, "
                "repetition, redundant description, and exposition before deleting any required scene beat. "
                f"The result MUST be under {maximum} words; aim for about {target}. Do not add commentary or control markers."
            ),
        },
        {
            "role": "user",
            "content": f"AUTHOR INSTRUCTION\n{author_prompt}\n\nDRAFT TO COMPRESS\n{draft}",
        },
    ]
    revised = _strip_markers(
        await generate(
            config,
            edit_messages,
            temperature=0.30,
            top_p=0.88,
            max_output_tokens=max(512, int(target * 1.35)),
        )
    )
    if revised and _word_count(revised) <= maximum and not _hard_quality_failure(revised):
        return revised

    # A second, tighter edit is preferable to returning prose that violates an explicit author ceiling.
    tighter_target = max(280, int(maximum * 0.72))
    edit_messages[0]["content"] = edit_messages[0]["content"].replace(
        f"aim for about {target}", f"aim for about {tighter_target}"
    )
    edit_messages[1]["content"] = f"AUTHOR INSTRUCTION\n{author_prompt}\n\nDRAFT TO COMPRESS\n{revised or draft}"
    revised2 = _strip_markers(
        await generate(
            config,
            edit_messages,
            temperature=0.20,
            top_p=0.85,
            max_output_tokens=max(512, int(tighter_target * 1.30)),
        )
    )
    if revised2 and _word_count(revised2) <= maximum and not _hard_quality_failure(revised2):
        return revised2
    raise RuntimeError(f"Model could not satisfy the author's hard {maximum}-word ceiling without a quality failure")


async def generate_complete_prose(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    min_words: int,
    max_passes: int = 6,
    max_output_tokens: int = 6144,
) -> str:
    contract = _length_contract_from_messages(messages)
    effective_passes = min(max_passes, 3) if contract.max_words is not None else max_passes
    text = await _original_generate_complete(
        config,
        messages,
        min_words=min_words,
        max_passes=effective_passes,
        max_output_tokens=max_output_tokens,
    )
    if contract.max_words is not None:
        text = await _compress_to_author_ceiling(config, messages, text, contract.max_words)
    return text


async def generate_complete_prose_streamed(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    min_words: int,
    on_delta,
    on_status=None,
    max_passes: int = 6,
    max_output_tokens: int = 6144,
) -> str:
    contract = _length_contract_from_messages(messages)
    effective_passes = min(max_passes, 3) if contract.max_words is not None else max_passes
    text = await _original_generate_complete_streamed(
        config,
        messages,
        min_words=min_words,
        on_delta=on_delta,
        on_status=on_status,
        max_passes=effective_passes,
        max_output_tokens=max_output_tokens,
    )
    if contract.max_words is not None and _word_count(text) > contract.max_words:
        if on_status is not None:
            await on_status(f"Tightening draft to the author's {contract.max_words}-word ceiling…")
        text = await _compress_to_author_ceiling(config, messages, text, contract.max_words)
    return text


def install_generation_reliability() -> None:
    generation.scene_word_floor = scene_word_floor
    generation.build_messages = build_messages
    generation.generate = generate
    generation.generate_complete_prose = generate_complete_prose

    # streaming_generation imported generate as generate_text at module load; patch both names.
    streaming.generate_text = generate
    streaming.generate_streamed = generate_streamed
    streaming.generate_complete_prose_streamed = generate_complete_prose_streamed
    streaming.verify_studio_scene_delivery = verify_studio_scene_delivery
    streaming._NoveltyStreamFilter = HardenedNoveltyStreamFilter

    # Generic stale-model repair remains prose-first. Adult explicit routing has its own
    # dedicated capability path and must not become the default for ordinary fiction.
    ollama_runtime._RECOMMENDED_MODELS = (
        GENERAL_PROSE_MODEL,
        CHARACTER_MODEL,
        FAST_MODEL,
        ADULT_EXPLICIT_MODEL,
        "HammerAI/rocinante-v1.1:12b-q4_K_M",
        "R4C3R/qwen2.5-14b-instruct-heretic:q4_k_m",
    )
