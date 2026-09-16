from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from difflib import SequenceMatcher

import httpx

from .generation import (
    MODEL_GATE,
    OLLAMA_CONTEXT_TOKENS,
    SCENE_COMPLETE_MARKER,
    SCENE_CONTINUE_MARKER,
    looks_abrupt_ending,
    requires_scene_complete_marker,
)
from .models import ProviderConfig
from .ollama_runtime import choose_installed_model, installed_ollama_models

DeltaCallback = Callable[[str], Awaitable[None]]
StatusCallback = Callable[[str], Awaitable[None]]
_MARKER_HOLDBACK = max(len(SCENE_COMPLETE_MARKER), len(SCENE_CONTINUE_MARKER)) + 24
_REPEAT_MIN_CHARS = 90
_REPEAT_PARAGRAPH_SIMILARITY = 0.78
_REPEAT_SENTENCE_SIMILARITY = 0.92
_REPEAT_RECENT_PARAGRAPHS = 18
_REPEAT_RECENT_SENTENCES = 48
_OLLAMA_REPEAT_PENALTY = 1.18
_OLLAMA_REPEAT_LAST_N = 512
_CONTINUATION_TAIL_CHARS = 12000


def _openai_chat_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+(?:['’-]\w+)?\b", text))


def _strip_scene_markers(text: str) -> tuple[str, bool, bool]:
    complete = SCENE_COMPLETE_MARKER in text
    wants_more = SCENE_CONTINUE_MARKER in text
    cleaned = text.replace(SCENE_COMPLETE_MARKER, "").replace(SCENE_CONTINUE_MARKER, "").strip()
    return cleaned, complete, wants_more


def _normalize_prose(text: str) -> str:
    return re.sub(r"[^\w]+", " ", text.casefold(), flags=re.UNICODE).strip()


def _similar(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right, autojunk=False).ratio()


def _sentence_parts(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?…])\s+", text.strip()) if part.strip()]


def _paragraph_parts(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]


def _recent_normalized_paragraphs(text: str) -> list[str]:
    values = [_normalize_prose(part) for part in _paragraph_parts(text)]
    return [value for value in values if value][-_REPEAT_RECENT_PARAGRAPHS:]


def _recent_normalized_sentences(text: str) -> list[str]:
    values: list[str] = []
    for paragraph in _paragraph_parts(text):
        values.extend(_normalize_prose(part) for part in _sentence_parts(paragraph))
    return [value for value in values if value][-_REPEAT_RECENT_SENTENCES:]


def dedupe_repetitive_prose(candidate: str, prior_text: str = "") -> tuple[str, int, float]:
    """Remove model-loop prose while preserving genuinely new scene movement.

    Returns (cleaned_text, removed_units, novelty_ratio). The ratio compares accepted words with
    model-produced words, so a paragraph loop cannot inflate completion progress simply by getting
    longer. This is deliberately conservative for short dialogue and brief rhetorical repetition.
    """
    original_words = _word_count(candidate)
    if not candidate.strip() or original_words == 0:
        return "", 0, 0.0

    paragraph_memory = _recent_normalized_paragraphs(prior_text)
    sentence_memory = _recent_normalized_sentences(prior_text)
    accepted: list[str] = []
    removed = 0

    for paragraph in _paragraph_parts(candidate):
        normalized_paragraph = _normalize_prose(paragraph)
        is_duplicate_paragraph = (
            len(paragraph) >= _REPEAT_MIN_CHARS
            and any(
                _similar(normalized_paragraph, previous) >= _REPEAT_PARAGRAPH_SIMILARITY
                for previous in paragraph_memory[-_REPEAT_RECENT_PARAGRAPHS:]
            )
        )
        if is_duplicate_paragraph:
            removed += 1
            continue

        kept_sentences: list[str] = []
        for sentence in _sentence_parts(paragraph):
            normalized_sentence = _normalize_prose(sentence)
            is_duplicate_sentence = (
                len(sentence) >= _REPEAT_MIN_CHARS
                and any(
                    _similar(normalized_sentence, previous) >= _REPEAT_SENTENCE_SIMILARITY
                    for previous in sentence_memory[-_REPEAT_RECENT_SENTENCES:]
                )
            )
            if is_duplicate_sentence:
                removed += 1
                continue
            kept_sentences.append(sentence)
            if normalized_sentence:
                sentence_memory.append(normalized_sentence)
                sentence_memory = sentence_memory[-_REPEAT_RECENT_SENTENCES:]

        cleaned_paragraph = " ".join(kept_sentences).strip()
        if not cleaned_paragraph:
            continue
        accepted.append(cleaned_paragraph)
        cleaned_normalized = _normalize_prose(cleaned_paragraph)
        if cleaned_normalized:
            paragraph_memory.append(cleaned_normalized)
            paragraph_memory = paragraph_memory[-_REPEAT_RECENT_PARAGRAPHS:]

    cleaned = "\n\n".join(accepted).strip()
    accepted_words = _word_count(cleaned)
    novelty_ratio = accepted_words / original_words if original_words else 0.0
    return cleaned, removed, novelty_ratio


async def generate_streamed(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    on_delta: DeltaCallback,
    temperature: float = 0.9,
    top_p: float = 0.95,
    json_mode: bool = False,
    max_output_tokens: int | None = None,
) -> str:
    """Generate while forwarding model text as it arrives.

    The ordinary generation path intentionally remains available for background tools and
    compatibility. This path is for interactive UI work where an author must be able to see
    that the model is actually producing text instead of staring at an empty spinner.
    """
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

            options: dict[str, float | int] = {
                "temperature": temperature,
                "top_p": top_p,
                "num_ctx": OLLAMA_CONTEXT_TOKENS,
                "repeat_penalty": _OLLAMA_REPEAT_PENALTY,
                "repeat_last_n": _OLLAMA_REPEAT_LAST_N,
            }
            if max_output_tokens is not None:
                options["num_predict"] = max_output_tokens
            body: dict = {
                "model": effective_model,
                "messages": messages,
                "stream": True,
                "keep_alive": "30m",
                "options": options,
            }
            if json_mode:
                body["format"] = "json"

            pieces: list[str] = []
            timeout = httpx.Timeout(connect=15.0, read=300.0, write=120.0, pool=15.0)
            try:
                async with (
                    httpx.AsyncClient(timeout=timeout, trust_env=False) as client,
                    client.stream(
                        "POST",
                        f"{config.base_url.rstrip('/')}/api/chat",
                        json=body,
                    ) as response,
                ):
                    if response.status_code >= 400:
                        payload = await response.aread()
                        detail = payload.decode("utf-8", errors="replace")[:500].strip()
                        raise RuntimeError(
                            f"Ollama could not generate with {effective_model}: "
                            f"{detail or f'HTTP {response.status_code}'}"
                        )
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise RuntimeError(
                                "Ollama returned an invalid streaming response"
                            ) from exc
                        if payload.get("error"):
                            raise RuntimeError(f"Ollama generation failed: {payload['error']}")
                        piece = str(payload.get("message", {}).get("content", ""))
                        if piece:
                            pieces.append(piece)
                            await on_delta(piece)
            except httpx.ReadTimeout as exc:
                raise RuntimeError(
                    "The local writing model stopped sending output for 5 minutes and "
                    "EmberWriter ended the stalled request."
                ) from exc
            except httpx.ConnectError as exc:
                raise RuntimeError(
                    "The local writing model server disconnected during generation. "
                    "EmberWriter will restart Ollama automatically on the next request."
                ) from exc

            content = "".join(pieces)
            if not content.strip():
                raise RuntimeError(f"Ollama returned an empty response from {effective_model}")
            return content

        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        request_body: dict = {
            "model": config.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
        }
        if max_output_tokens is not None:
            request_body["max_tokens"] = max_output_tokens

        pieces: list[str] = []
        timeout = httpx.Timeout(connect=15.0, read=300.0, write=60.0, pool=15.0)
        async with (
            httpx.AsyncClient(timeout=timeout) as client,
            client.stream(
                "POST",
                _openai_chat_url(config.base_url),
                headers=headers,
                json=request_body,
            ) as response,
        ):
            response.raise_for_status()
            async for line in response.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = payload.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                piece = str(delta.get("content", "") or "")
                if piece:
                    pieces.append(piece)
                    await on_delta(piece)

        content = "".join(pieces)
        if not content.strip():
            raise RuntimeError("Model returned no streamed text")
        return content


class _MarkerFilter:
    """Keep control markers out of the visible author-facing stream."""

    def __init__(self, emit: DeltaCallback) -> None:
        self._emit = emit
        self._pending = ""

    async def feed(self, piece: str) -> None:
        self._pending += piece
        if len(self._pending) <= _MARKER_HOLDBACK:
            return
        safe = self._pending[:-_MARKER_HOLDBACK]
        self._pending = self._pending[-_MARKER_HOLDBACK:]
        safe = safe.replace(SCENE_COMPLETE_MARKER, "").replace(SCENE_CONTINUE_MARKER, "")
        if safe:
            await self._emit(safe)

    async def finish(self) -> None:
        safe = self._pending.replace(SCENE_COMPLETE_MARKER, "").replace(SCENE_CONTINUE_MARKER, "")
        self._pending = ""
        if safe:
            await self._emit(safe)


class _NoveltyStreamFilter:
    """Buffer paragraphs so degenerative repetition never reaches the author-facing preview."""

    def __init__(self, emit: DeltaCallback, prior_text: str = "") -> None:
        self._emit = emit
        self._prior_text = prior_text
        self._buffer = ""
        self._accepted: list[str] = []
        self.removed_units = 0
        self.raw_words = 0

    @property
    def text(self) -> str:
        return "\n\n".join(self._accepted).strip()

    @property
    def novelty_ratio(self) -> float:
        return _word_count(self.text) / self.raw_words if self.raw_words else 0.0

    async def feed(self, piece: str) -> None:
        self._buffer += piece
        while True:
            match = re.search(r"\n\s*\n", self._buffer)
            if not match:
                break
            paragraph = self._buffer[: match.start()]
            self._buffer = self._buffer[match.end() :]
            await self._accept(paragraph)

    async def finish(self) -> None:
        if self._buffer.strip():
            await self._accept(self._buffer)
        self._buffer = ""

    async def _accept(self, paragraph: str) -> None:
        if not paragraph.strip():
            return
        self.raw_words += _word_count(paragraph)
        prior = self._prior_text
        if self._accepted:
            prior = f"{prior}\n\n{'\n\n'.join(self._accepted)}".strip()
        cleaned, removed, _ = dedupe_repetitive_prose(paragraph, prior)
        self.removed_units += removed
        if not cleaned:
            return
        separator = "\n\n" if self._accepted else ""
        self._accepted.append(cleaned)
        await self._emit(f"{separator}{cleaned}")


async def generate_complete_prose_streamed(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    min_words: int,
    on_delta: DeltaCallback,
    on_status: StatusCallback | None = None,
    max_passes: int = 6,
    max_output_tokens: int = 6144,
) -> str:
    """Generate a complete scene while making every non-repetitive pass visible."""
    accumulated = ""
    working_messages = list(messages)
    marker_required = requires_scene_complete_marker(messages)
    repetition_recoveries = 0

    for pass_index in range(max_passes):
        if on_status is not None:
            label = (
                "Writing scene…"
                if pass_index == 0
                else f"Continuing scene · pass {pass_index + 1}…"
            )
            await on_status(label)

        novelty_filter = _NoveltyStreamFilter(on_delta, accumulated)
        marker_filter = _MarkerFilter(novelty_filter.feed)
        raw = await generate_streamed(
            config,
            working_messages,
            on_delta=marker_filter.feed,
            max_output_tokens=max_output_tokens,
        )
        await marker_filter.finish()
        await novelty_filter.finish()

        _raw_cleaned, complete, wants_more = _strip_scene_markers(raw)
        cleaned = novelty_filter.text
        candidate_words = _word_count(cleaned)
        raw_words = max(novelty_filter.raw_words, 1)
        repetition_detected = (
            raw_words >= 100
            and (
                novelty_filter.removed_units >= 2
                or novelty_filter.novelty_ratio < 0.55
            )
        )

        if cleaned:
            if accumulated:
                await on_delta("\n\n")
            accumulated = f"{accumulated}\n\n{cleaned}".strip()

        if repetition_detected:
            repetition_recoveries += 1
            complete = False
            wants_more = True
            if on_status is not None:
                await on_status(
                    "Repetition loop detected · discarded repeated prose · advancing to a new beat…"
                )
        else:
            repetition_recoveries = 0

        words = _word_count(accumulated)
        abrupt = looks_abrupt_ending(accumulated)
        if complete and words >= min_words and not abrupt and candidate_words > 0:
            return accumulated
        if (
            words >= min_words
            and not wants_more
            and pass_index > 0
            and not marker_required
            and not abrupt
        ):
            return accumulated
        if pass_index == max_passes - 1:
            return accumulated

        remaining = max(min_words - words, 0)
        continuation_instruction = (
            "Continue the SAME scene from the exact final state below. Advance immediately into a NEW beat. "
            "Do not restart, recap, paraphrase, recycle prior sentences, or repeat the same action with different adjectives. "
            "Every paragraph must change the physical action, dialogue, emotional state, magical state, or consequence. "
            "Do not linger on generic steam/heat/body-close language when the scene objective requires progression. "
            "Finish the author's requested scene objective and its immediate consequence. Do not stop mid-word or mid-sentence."
        )
        if repetition_detected:
            continuation_instruction += (
                " Your previous attempt was rejected because it repeated existing prose. Break the loop now: use fresh verbs, "
                "fresh sentence structures, new dialogue or action, and move forward rather than restating the current moment."
            )
        if repetition_recoveries >= 2:
            continuation_instruction += (
                " You have repeated twice. Skip directly to the next irreversible story beat and continue from there without "
                "describing the same contact, setting sensation, or anticipation again."
            )
        if marker_required:
            continuation_instruction += (
                " This is an intimacy scene: buildup, kissing, and initial escalation are not completion. Continue until the "
                "requested encounter and its immediate aftermath/changed state have genuinely landed."
            )
        if remaining:
            continuation_instruction += (
                f" The accepted draft is still roughly {remaining} words short of the requested scene floor. Repeated words do not count."
            )
        continuation_instruction += (
            f" End with {SCENE_COMPLETE_MARKER} only after the scene has genuinely concluded; otherwise end with "
            f"{SCENE_CONTINUE_MARKER}."
        )

        handoff = accumulated[-_CONTINUATION_TAIL_CHARS:]
        working_messages = [
            *messages,
            {
                "role": "assistant",
                "content": handoff,
            },
            {
                "role": "user",
                "content": continuation_instruction,
            },
        ]

    return accumulated
