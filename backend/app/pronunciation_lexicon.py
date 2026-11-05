"""Author-owned IPA phoneme lexicon for local Kokoro narration.

Kokoro's eSpeak G2P chooses a default dialect. The author can choose a
contextual pronunciation for a word, without respelling prose or affecting
homophones. Exact matched tokens get an IPA override; all other words use
the standard Kokoro phonemizer in their selected voice locale.
"""
from __future__ import annotations

import re

MAX_OVERRIDES = 150
TERM = re.compile(r"^[A-Za-z][A-Za-z'’-]{0,79}$")
# No whitespace, markup or unknown phonemes is accepted from the author.
# Model-specific Unicode inventory is checked against engine.tokenizer.vocab.
PREFERRED_EN_US = {
    "buoy": "bˈuːi",
    "buoys": "bˈuːiz",
}


def validate_rule(term: str, ipa: str) -> tuple[str, str]:
    written = term.strip()
    phonemes = ipa.strip()
    if not TERM.fullmatch(written):
        raise ValueError("IPA override is for one written word (max 80 characters)")
    if not 1 <= len(phonemes) <= 100 or any(
        c.isspace() or c in "<>/\\\n\r" or ord(c) < 32 for c in phonemes
    ):
        raise ValueError("IPA pronunciation must contain supported, unspaced phonemes only")
    return written, phonemes


def phonemize_author_text(text: str, rules: list[dict], tokenizer, lang: str) -> str:
    """Apply authored IPA exactly where the original written word occurs.

    Preserve punctuation in the phonemized model input. Do not replace all
    occurrences of a phoneme sequence, since 'buoys' and 'boys' can be
    homophones in ordinary regional speech.
    """
    if not rules:
        return tokenizer.phonemize(text, lang)
    if len(rules) > MAX_OVERRIDES:
        raise ValueError("IPA override library is full")
    entries = {}
    for rule in rules:
        word, ipa = validate_rule(rule["written"], rule["ipa"])
        if tokenizer.known(ipa) != ipa:
            raise ValueError(f"IPA pronunciation for {word} contains unsupported model phonemes")
        entries[word.casefold()] = ipa
    pattern = re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(k) for k in sorted(entries, key=len, reverse=True))
        + r")(?!\w)", re.IGNORECASE
    )
    chunks = []
    cursor = 0
    for match in pattern.finditer(text):
        prefix = text[cursor:match.start()]
        if prefix:
            chunks.append(tokenizer.phonemize(prefix, lang))
        chunks.append(entries[match.group().casefold()])
        cursor = match.end()
    if cursor < len(text):
        chunks.append(tokenizer.phonemize(text[cursor:], lang))
    # Explicit spaces preserve word boundaries while the model retains
    # the normalized IPA; no graphemes are sent as phonemes.
    return " ".join(part.strip() for part in chunks if part.strip())


def reference_examples() -> dict:
    return {
        "description": "Author-controlled American English phonemes for Kokoro. "
                       "Standard words use eSpeak; only selected words override G2P.",
        "examples": [
            {"written": "buoy", "ipa": "bˈuːi",
             "guide": "BOO-ee (US variant; not boy)"},
            {"written": "buoys", "ipa": "bˈuːiz",
             "guide": "BOO-eez (US plural)"},
        ],
        "reference": "Cambridge English Pronouncing Dictionary (IPA variants); "
                     "Carnegie Mellon Pronouncing Dictionary (US ARPAbet)",
        "note": "Listen to a rehearsal before committing a pronunciation. "
                "A phonetic guide is not proof of satisfactory audio.",
    }


# The bundled CMU Pronouncing Dictionary is a BSD-licensed American-English
# lexicon. We offer its pronunciations to the author as choices, rather than
# automatically changing every possible homograph.
from functools import lru_cache
from pathlib import Path

_CMUDICT = Path(__file__).parent / "resources" / "cmudict.dict"
_ARPABET_TO_IPA = {
    "AA": "ɑ", "AE": "æ", "AH": "ʌ", "AO": "ɔ", "AW": "aʊ",
    "AY": "aɪ", "EH": "ɛ", "ER": "ɝ", "EY": "eɪ", "IH": "ɪ",
    "IY": "i", "OW": "oʊ", "OY": "ɔɪ", "UH": "ʊ", "UW": "uː",
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f",
    "G": "ɡ", "HH": "h", "JH": "dʒ", "K": "k", "L": "l",
    "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "ɹ",
    "S": "s", "SH": "ʃ", "T": "t", "TH": "θ", "V": "v",
    "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}


def _convert_arpa(phones: list[str]) -> str:
    output = []
    for phone in phones:
        base = re.sub(r"[012]$", "", phone)
        if base not in _ARPABET_TO_IPA:
            raise ValueError("Unsupported dictionary phoneme: " + phone)
        suffix = phone[-1] if phone[-1].isdigit() else ""
        if base == "AH" and suffix == "0":
            sound = "ə"
        elif base == "ER" and suffix == "0":
            sound = "ɚ"
        else:
            sound = _ARPABET_TO_IPA[base]
        mark = "ˈ" if suffix == "1" else ("ˌ" if suffix == "2" else "")
        output.append(mark + sound)
    return "".join(output)


@lru_cache(maxsize=1)
def _cmu_entries() -> dict[str, list[list[str]]]:
    # Bundled dictionary avoids any network request during author workflows.
    if not _CMUDICT.is_file():
        return {}
    choices: dict[str, list[list[str]]] = {}
    with _CMUDICT.open(encoding="utf-8") as handle:
        for line in handle:
            bits = line.split()
            if len(bits) <= 1 or bits[0].startswith(";;;"):
                continue
            word = re.sub(r"\(\d+\)$", "", bits[0]).casefold()
            if not TERM.fullmatch(word):
                continue
            variants = choices.setdefault(word, [])
            phones = bits[1:]
            if phones not in variants and len(variants) < 8:
                variants.append(phones)
    return choices


def dictionary_lookup(word: str) -> dict:
    written = word.strip()
    if not TERM.fullmatch(written):
        raise ValueError("Look up one written word")
    choices = _cmu_entries().get(written.casefold(), [])
    return {
        "written": written,
        "source": "Carnegie Mellon Pronouncing Dictionary (US English)",
        "license": "BSD (see bundled CMUDICT-LICENSE)",
        "variants": [
            {"arpa": " ".join(phones), "ipa": _convert_arpa(phones)}
            for phones in choices
        ],
        "note": "Dictionary pronunciations are suggestions. Choose and rehearse; "
                "the author decides which regional or contextual pronunciation is correct.",
    }
