from __future__ import annotations

import json
import re

from .craft import save_voice_profile
from .generation import generate
from .models import ProviderConfig, VoiceProfile
from .storage import project_root, read_text

MAX_SAMPLE_CHARS = 48000
MAX_FILES = 12


def _manuscript_paths(slug: str) -> list[str]:
    root = project_root(slug)
    if not (root / "project.json").exists():
        raise FileNotFoundError(slug)
    manuscript = root / "manuscript"
    if not manuscript.exists():
        return []
    paths: list[str] = []
    for path in sorted(manuscript.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
            paths.append(str(path.relative_to(root)).replace("\\", "/"))
    return paths


def _representative_paths(paths: list[str]) -> list[str]:
    if len(paths) <= MAX_FILES:
        return paths
    indexes = {round(index * (len(paths) - 1) / (MAX_FILES - 1)) for index in range(MAX_FILES)}
    return [paths[index] for index in sorted(indexes)]


def _sample_file(text: str, budget: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= budget:
        return cleaned
    third = max(300, budget // 3)
    middle_start = max(0, len(cleaned) // 2 - third // 2)
    return "\n…\n".join(
        [cleaned[:third], cleaned[middle_start : middle_start + third], cleaned[-third:]]
    )[:budget]


def build_manuscript_voice_sample(slug: str) -> tuple[str, list[str]]:
    paths = _representative_paths(_manuscript_paths(slug))
    if not paths:
        raise ValueError("No manuscript prose is available to learn from")
    per_file = max(1200, MAX_SAMPLE_CHARS // len(paths))
    chunks: list[str] = []
    used: list[str] = []
    remaining = MAX_SAMPLE_CHARS
    for path in paths:
        if remaining <= 0:
            break
        try:
            text = read_text(slug, path)
        except (FileNotFoundError, OSError, ValueError):
            continue
        sample = _sample_file(text, min(per_file, remaining))
        if len(sample.strip()) < 200:
            continue
        chunks.append(f"\n--- SOURCE: {path} ---\n{sample}")
        used.append(path)
        remaining -= len(sample)
    if not chunks:
        raise ValueError("Manuscript files do not contain enough prose to learn a voice")
    return "\n".join(chunks), used


def _parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Voice Fingerprint did not return a JSON object")
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("Voice Fingerprint returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise TypeError("Voice Fingerprint returned an invalid payload")
    return payload


async def analyze_manuscript_voice(
    slug: str,
    provider: ProviderConfig,
    profile_name: str,
) -> tuple[VoiceProfile, list[str]]:
    sample, sources = build_manuscript_voice_sample(slug)
    system = """You are EmberWriter's Voice Fingerprint analyst.
Return ONLY valid JSON matching the requested schema. Analyze reusable prose technique, not story facts.

This is a manuscript-wide fingerprint, not generic writing advice. Find habits that recur across different scenes while preserving useful irregularity. Distinguish deliberate voice from accidental errors.

Study sentence-length variation, fragments, punctuation, paragraph cadence, diction, contractions, humor, understatement, repetition, imagery, dialogue rhythm, subtext, interiority, point-of-view distance, and transitions. Identify how characters sound different from one another when the samples support it.

Identify generic model-writing habits the author does not normally use, such as over-explaining, overly symmetrical phrasing, generic sensory inventories, repeated emotional labels, fake-poetic abstraction, polished therapy language, and interchangeable banter. Put those in avoidances.

Describe techniques concretely enough to guide fresh prose without copying sentences from the samples. Do not quote long passages.
"""
    user_message = f"""PROFILE NAME: {profile_name}

Return this JSON shape:
{{
  "name": "profile name",
  "prose_directive": "detailed author fingerprint directive",
  "sentence_rhythm": "cadence, syntax, punctuation, fragments and paragraph habits",
  "diction": "register and word-choice habits",
  "imagery": "metaphor and image habits",
  "dialogue": "dialogue rhythm, subtext, tags, interruptions, humor and differentiation",
  "interiority": "how thought and emotion are rendered",
  "pov_distance": "narrative distance and filtering",
  "sensual_voice": "relationship and attraction prose technique when evidenced, otherwise note limited evidence",
  "signature_traits": ["repeatable human author trait"],
  "avoidances": ["generic or model-like tendency to avoid"]
}}

REPRESENTATIVE MANUSCRIPT SAMPLES
{sample}
"""
    raw = await generate(
        provider,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ],
        temperature=0.22,
        top_p=0.88,
        json_mode=True,
    )
    profile = VoiceProfile.model_validate(_parse_json_object(raw))
    save_voice_profile(slug, profile)
    return profile, sources
