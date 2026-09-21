from __future__ import annotations

# EmberWriter's managed local capability slots.
#
# The explicit specialist was empirically proven on 2026-09-20 with the Q4_K_M
# quantization under llama.cpp. Its fine-tune/redistribution license still requires
# commercial review before EmberWriter bundles or hosts the weights.
ADULT_EXPLICIT_MODEL = "hf.co/mradermacher/Qwen3.5-4B-NSFW-ARA-Heretic-Literotica-i1-GGUF:Q4_K_M"
GENERAL_PROSE_MODEL = "hf.co/mradermacher/magnum-v4-12b-GGUF:Q4_K_M"
CHARACTER_MODEL = "hf.co/mradermacher/Pygmalion-3-12B-GGUF:Q4_K_M"
PLANNING_MODEL = "R4C3R/qwen3-8b-heretic:q4_k_m"
FAST_MODEL = PLANNING_MODEL

LEGACY_HIGH_HEAT_MODEL = "Fermi/Cydonia-24B-v4.3-heretic-vision:Q4_K_M"
LEGACY_ROCINANTE_MODEL = "hf.co/mradermacher/Rocinante-X-12B-v1-Heretic-Uncensored-GGUF:Q4_K_M"

MANAGED_AUTO_MODELS = (
    ADULT_EXPLICIT_MODEL,
    GENERAL_PROSE_MODEL,
    CHARACTER_MODEL,
    FAST_MODEL,
)

CAPABILITY_MODELS = {
    "adult_explicit": ADULT_EXPLICIT_MODEL,
    "general_prose": GENERAL_PROSE_MODEL,
    "character": CHARACTER_MODEL,
    "planning": PLANNING_MODEL,
    "fast": FAST_MODEL,
}

ADULT_EXPLICIT_FAMILY = "qwen3.5-4b-nsfw-ara-heretic-literotica"
