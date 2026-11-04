# Audiobook Production — Local QC, Pacing and Chapter-Marked M4B

The Audiobook Workshop is in **Publish → Audiobook**. Existing Windows SAPI
narration, individual WAV/MP3 downloads, restart-recoverable Binder-order
whole-book jobs and chapter ZIP packages remain available.

## New author controls

- **Pacing** — SAPI speech rate can be adjusted from -5 (slower) through +5
  (faster); previous default is -1. Rate is stored in a whole-book batch job
  and participates in audio cache fingerprints, so changing the rate does not
  silently reuse an earlier track.
- **Audio readiness** — on demand, checks the exact Binder-ordered audio batch,
  source manuscript SHA-256 identity, manifest provenance, WAV header,
  duration, channels, sample rate, and obvious silent openings. MP3 tracks are
  inspected with FFprobe when installed. Missing FFprobe gives an explicit
  unverified status, never a passing grade.
- **Stale audio protection** — ZIP export refuses to package a completed
  audiobook if the source chapter text changed since narration was queued.
  The quality report also catches legacy recordings that have no source hash,
  missing or corrupted tracks, unknown MP3 integrity and incomplete jobs.
- **Single-file chapter-marked M4B** — after a successful technical readiness
  report, an author can trigger an *optional* local FFmpeg/FFprobe AAC build.
  The exported M4B contains an audible single audio stream, chapter markers
  in original Binder order, and chapter names. Output is verified using FFprobe
  before atomically replacing any previous M4B file. The manuscript is checked
  again for staleness after encoding. No cloud service sees the text.
- **Less interface clutter** — audio tracks and the entire chapter narration
  ledger are collapsed until requested. The author sees the current queue,
  pacing settings and one clear readiness action first.

## Important limitations

SAPI is **system-voice narration** (not professional multi-actor acting).
Neither technical checks nor a successful M4B build prove accurate spoken
words, natural pronunciation, pacing, dynamics, loudness, retail compliance
or artistic suitability. Listen to all chapters. This is not an ACX master,
professional audio mix or retailer-accepted product.

M4B encoding runs on explicit request and depends on local FFmpeg + FFprobe.
It uses a finite synchronous compile, not yet a resumable encoding queue.
Missing binaries or incompatible chapter formats are surfaced as errors.
The chapter-by-chapter narration queue remains persistent and resumable.
The final M4B stream is encoded to 44.1kHz AAC, but mixed input sample
rates or heterogeneous existing track formats may require regenerating
chapters before a successful compile.

The optional synthetic integration test actually uses installed FFmpeg to
create an AAC M4B and reads its chapter markers with FFprobe. All test
manuscripts are fictional and isolated from private author projects.

## Continuity and editorial developments in the same release

Book Studio now retrieves bounded, relevant *verbatim interior paragraphs*
from previous chapters using keywords from the upcoming chapter brief,
attaching source chapter and line information. This is deterministic local
retrieval, not an ungrounded generative memory summary. Author canon and the
preceding chapter ending remain prioritized, and overall prompt context stays
within its existing character budget.

Prose Editor recognizes a short, conservative set of common spelling typos
(e.g. `definately` → `definitely`). Each correction remains an *optional*
source-versioned author decision with a restorable snapshot; this is not a
full offline grammar engine.

## Future audiobook milestones

- Private per-character pronunciation lexicon and word/phoneme exceptions.
- Audio proof-listening notes, timestamped QC and narrator correction takes.
- Optional multi-voice scenes and character-specific narration profiles.
- Peak/RMS/loudness normalization and integrated LUFS/true-peak reports.
- A dedicated restart-resumable M4B encoding queue and supported cover-art
  embedding, plus separate retail-preset readiness profiles.
