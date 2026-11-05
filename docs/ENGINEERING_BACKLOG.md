# EmberWriter Engineering Backlog — After Offline M4B Job and RMS Release

This is an implementation status ledger, not a product promise. A UI button
is not evidence that a feature meets retailer or literary-quality standards.

## Shipped and verified so far

- Author-first local Book Studio: structured plan, local outline proposal,
  candidate chapters, explicit approval, and persistent whole-book drafting.
- Canon review, basic editorial and independent reader evaluation, source-
  attributed retrieval of relevant passages from earlier chapters, and
  deterministic grammar/typo assistance with author-controlled application.
- Offline Windows SAPI narration, per-chapter voice/pace, private spoken
  substitutions, chapter-by-chapter proof notes, restart-aware whole-book
  narration, chapter ZIPs, and chapter-marked original M4B.
- Full-book two-pass optional loudness-leveling into separate M4B, with
  objectively measured integrated LUFS, true peak and LRA.
- **Current release:** author-visible persistent M4B encode queue with
  cooperative resource scheduling, subprocess cancellation, safe file staging,
  restart recovery by re-encoding verified chapters, and a validated download
  route. Added actual RMS dBFS and quiet-passage detection. Results are
  source-hash cached with schema version 2.
- Responsive 1440/900/390px browser smoke testing; publishing and advanced
  audiobook controls stay scoped and collapsed rather than becoming new tabs.
- Synthetic regression tests, genuine local FFmpeg AAC/M4B conversion and
  loudness tests, and fresh-clone public source verification.

## Outstanding high-impact engineering

### P0 — before claiming a professional audiobook
1. **Character-level multi-voice casting**. Explicit dialogue-speaker
   assignment in the manuscript or scene breakdown; local voice providers
   with legally usable models, phrase-to-voice alignment, natural transitions,
   narrator consistency and an author approval interface. Chapter voice
   overrides do **not** implement this.
2. **True background/room noise-floor tests**. Detect gaps or intentionally
   silent passages and measure their room-tone RMS separately, distinguishing
   noise, hum, hiss and dead digital silence. Never substitute the FFmpeg
   aggregate `astats Noise_floor` reading as microphone noise. Retailer
   profiles must use their *actual* published measurement definitions.
3. **Retailer-specific mastering and export profiles**. Exact format,
   peak, RMS, noise, title/metadata and chapter-delivery specifications for
   each target retailer, with profile version, current rules citation,
   loudness standard and test fixtures. No current generic pass report
   guarantees ACX or other retailer acceptance.
4. **Human proof-listening signoff**. Complete audio timelines, per-take
   verification, corrections and approval workflow, plus comprehensive
   source-audio alignment. The current timestamped note ledger is a
   foundation, not a completeness guarantee.
5. **M4B queue multi-worker and crash hardening**. One server process is
   supported. Add OS-level project locks, process ownership leases, explicit
   stale-worker fencing and stronger external Ollama/TTS resource accounting.
   Restart recovery re-encodes the whole M4B; partial AAC checkpoints are
   not implemented. A forcibly killed OS process may leave an orphaned
   external FFmpeg process requiring inspection on restart.

### P1 — novel editorial quality and continuity
6. **Cross-chapter semantic contradictions**. Extract proposed facts with
   confidence and actual manuscript source quotes; compare dates, ages,
   locations, object states, promises, knowledge and relationships; allow
   explicit author canon decisions. Avoid presenting model inferences as facts.
7. **Broader offline grammar and style**. Integrate a supported, versioned
   local proofing engine (with no unapproved cloud requests), line-anchored
   alternatives, false-positive controls for fantasy vocabulary and dialect,
   and bulk-diff previews before author approval.
8. **Long-context retrieval and author memory**. Better text segmentation,
   retrieval evaluation sets, citations, chapter recency balancing and
   narrative arc reminders, with hard privacy and character-budget limits.
9. **Automated revision pipeline**. Independent editor passes, safe grouped
   edits, quantitative tests for story and voice preservation, author review,
   and conflict detection against later manuscript edits.

### P2 — production maturity
10. Audiobook cover-art embedding and metadata validation for each outlet.
11. Portable non-Windows audio engine options with licensing/voice consent
    protections and offline privacy controls.
12. Performance and memory stress tests on a real-length **synthetic**
    manuscript; protected private manuscript smoke checks only with explicit
    author permission.
13. Richer progress telemetry, estimated queue capacity, stop/retry controls,
    and cross-process locks for AI writing, critique and audio workers.
14. Keyboard-only, screen-reader and high-zoom accessibility walkthroughs.

## UX release rule

Do not add more top-level navigation for each backlog item. Narration and
mastering live in **Publish → Audiobook**; manuscript editorial work lives
in **Plan → Edit & review**. Show one primary action, hide expert diagnostics
under an opt-in expansion, and rerun the existing responsive smoke test.

## Safety and verification rule

Never commit the private novel, credentials, production recordings, or the
current live Pinokio project data. Use isolated synthetic fixtures and verify
the exact public repository revision after pushing.
