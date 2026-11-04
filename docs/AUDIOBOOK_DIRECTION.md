# Narration Direction and Proof Listening

**Publish → Audiobook** now contains two optional, collapsed author controls.
The main whole-book narration, readiness scan and M4B export remain prominent.

## Pronunciation dictionary

Create a project-local list of written terms and plain-language spoken
substitutions (up to 150). For example, the fictional written name
`Aster Vale` could be spoken as `AS-ter VAYL`. The replacement is applied
**only** to the private temporary text sent to Windows SAPI. It never rewrites
the author’s Markdown, changes chapters, alters worldbuilding, calls cloud TTS,
or imports a publicly hosted pronunciation list. Substitutions are
word-boundary aware, case-insensitive, longest phrase first, and are applied
in one pass so replacement text is not recursively modified.

This is not a phonetic engine, IPA parser, SSML library, or guaranteed voice
pronunciation. Listen to the actual result; installed SAPI voices differ.

## Chapter narrator profiles

The author can select an installed Windows narrator and speech pace for each
**entire chapter**, overriding the default settings for that chapter in a
whole-book batch. This is not character-by-character voice acting, and it
does not identify quoted speakers or attempt dialogue attribution.

The currently selected narrator and full dictionary are snapshotted in a
durable batch job. Narration output cache fingerprints include the manuscript,
narrator, pacing, spoken text and settings revision. Changes during a batch
stop for author review rather than producing a mixed-version audiobook.

## Timed proof notes

After producing chapter audio, authors can record timestamped issues and
corrections tied to the current audio file. The list supports Resolve and
Reopen and links to the appropriate chapter player without automatically
starting playback. Notes for older recordings remain historical, not silently
reattached to a newer take.

Outstanding notes tied to current tracks block technical M4B readiness and
the current whole-book ZIP export. After repairing the audio, resolve the
note or create a new take. Only the author can mark notes resolved.

Settings, notes and manifests live under the current project's private
`.ember/` folder. They are excluded from the public code repository.

## Cooperative resource slot

Within one active EmberWriter Python server process, supported heavy jobs
share one asynchronous resource slot: Book Studio chapter generation and
outlining, the independent Reader Panel evaluation call, automatic or manual
Windows narration. Requests wait rather than automatically competing for
the same local inference/CPU resources.

The reservation is **cooperative and process-local**. It does not globally
lock other Ollama clients, independently launched model bakeoffs, unrelated
generation endpoints, or multiple backend worker processes. Cancellation of
a thread-backed narration can release the reservation before the physical
speech subprocess terminates; further lifecycle hardening remains planned.
The author may still run another tool externally. Do not advertise a
global resource governor or hardware utilization guarantees.

## Release verification

Synthetic tests cover project isolation, substitution correctness, frozen
settings during generation, speech pacing/voice parameters, proof notes,
invalid input, stale audio rejection and cross-job serialization. The
existing end-to-end FFmpeg M4B integration still verifies source identity
and chapter markers.

Visual browser tests verify that the two new panels are collapsed by default,
that expanding pronunciation controls does not overflow at 1440, 900, or
390 CSS pixels, and that the main Narrate entire book action remains visible
before the optional controls.

Still outstanding: scene-level multi-actor casting and automatic speaker
identification, high-fidelity voice models, retail loudness mastering,
true peak analysis, and dedicated resumable M4B encoding.
