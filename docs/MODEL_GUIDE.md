# EmberWriter model guide

EmberWriter uses different local models for different writing jobs. One model does not have to be best at everything.

## Mature / relationship fiction

**Recommended:** `HammerAI/rocinante-v1.1:12b-q4_K_M`

Use this for character-led romance, harem, kink, adult relationship scenes, roleplay-heavy chapters, and dialogue where personality matters more than analytical precision. Rocinante is a story/RP-tuned 12B model rather than a general instruct model with refusal suppression layered on top.

## General fiction

**Recommended:** `ministral-3:14b` on machines with enough memory; `ministral-3:8b` is the lighter alternative.

Use this for regular chapters, action, worldbuilding, dialogue, revision, mystery, horror, fantasy, and other scenes where adult-roleplay specialization is not the main requirement. It has strong instruction following and a large context window.

## Planning / story logic

**Recommended:** `qwen3:8b`

Use this for brainstorming, outlines, continuity checking, critique, alternative plot paths, and story-room problem solving. EmberWriter treats it as a planning model, not the preferred final-prose voice.

## Why EmberWriter uses model-aware sampler presets

Different model families publish or imply different sampling behavior. EmberWriter therefore no longer forces every local model through the same temperature, top-p, and repetition settings. The model-purpose layer picks a conservative preset for each known model family while still allowing custom installed models.

Saved AI Studio output is also excluded from automatic Studio retrieval so a weak generation cannot become a style example for the next generation.
