# Offline Loudness Analysis and Optional Leveled M4B

**Publish → Audiobook → Check audio readiness → Advanced: loudness and peak inspection**

This remains an optional, collapsed step. It does not add another main workspace
or interfere with the author's primary narration controls.

## Engineering analysis

The author initiates a local FFmpeg scan to measure each completed,
source-verified chapter's **integrated loudness (LUFS)**, **true peak (dBTP)**
and **loudness range (LRA)**. Results are shown per chapter and cached under
the private project `.ember/audiobook/` directory with SHA-256 fingerprints
of the media bytes. When a chapter is rewritten, re-rendered, corrupted or
renamed, the readiness gate and hash checks invalidate old measurements.

The tool flags potentially excessive peaks (above -1.0 dBTP) and chapters
outside a broad, intentionally advisory -24 to -14 LUFS listening band.
The author must still listen to every chapter and judge pacing and balance.

**These are not ACX/Audible/Kobo/Apple Books retailer compliance presets.**
The optional -18 LUFS / -2 dBTP leveling target is an internal listening
reference; LUFS is not the same metric as RMS and cannot be substituted for
a retailer's technical requirements.

## Optional two-pass M4B leveling

After the current book passes technical audio readiness and local loudness
measurements have been run, the author may opt to build an additional,
chapter-marked **leveled M4B**. The process:

1. Concatenates approved chapters in Binder order in the FFmpeg input pipeline.
2. Measures the **whole book** using the FFmpeg `loudnorm` filter, preserving
   its relative chapter-to-chapter dynamics.
3. Reencodes the whole book using measured input loudness, true peak, LRA and
   threshold offsets. It does *not* permanently alter chapter audio.
4. Inspects the resulting AAC file, requires the correct chapter marker count,
   checks measured output loudness/peak are reasonably close to the selected
   listening target, and rechecks manuscript readiness before finalization.
5. Writes a separate `current-book-narration-leveled.m4b`, leaving the
   original non-leveled M4B and all WAV/MP3 narration intact.

A failed encode or unexpectedly poor output leaves any previous completed
artifact intact. Full-length encoding can be expensive and at present runs
on explicit request, **not** in a durable, separately resumable job queue.

## Quality boundaries and next steps

Loudness measurements do not establish that speech is intelligible, dialogue
is expressive, pronunciation is correct or the retailer's requirements are
met. This release does not support automated noise-floor or RMS retailer
presets, speaker-level voice acting, integrated listen-through approval or
professional mastering guarantees.

Tests use **actual FFmpeg and FFprobe** on deliberately synthetic WAV tone
sources and assert separate output artifacts, measurable loudness, peak
headroom, source-revision rejection and cached provenance.

For private narration profiles and author proof-listening notes, see
`docs/AUDIOBOOK_DIRECTION.md`.
