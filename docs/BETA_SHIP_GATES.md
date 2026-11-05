# EmberWriter Beta: three non-negotiable ship gates

**Decision:** HOLD PUBLIC BETA. 0.15.0-rc.1 is a developer/author test candidate, not a beta-ready release. An API that produces a few paragraphs or minutes of neural audio is not proof of full-length production quality.

## Gate 1 — A complete novel with author-controlled prose quality

EmberWriter must produce a **beginning-to-end fictional novel** with a reproducible writing workflow on supported local hardware, not merely create an outline or incomplete chapters. The test edition should include **at least 60,000 finished words across at least 20 substantive chapters**, all in the intended Binder order. Every draft must remain candidate-only until reviewed and explicitly accepted. The source text must survive restart and EPUB/DOCX export; no invented authority can silently overwrite author prose.

**Two independent assessments are required:**

- **Automation:** Compare approved chapter count against planned count; validate chapter word counts, manuscript hashes and export ordering; flag unfinished placeholders, near-duplicate paragraphs, excessive repeated phrases, dropped plot threads and unsupported character/canon changes. Report findings with source excerpts, never silently rewrite.
- **Author/editor reading:** Read the **entire book**, score voice originality, narrative causality, scene specificity, character differentiation, meaningful consequences, continuity, pacing and ending quality. The author must confirm that the novel is coherent and sounds like *their* story; quality cannot be certified by keyword heuristics or an AI self-critique.

**Passing is not a promise that all possible generations will be good.** It means the tested workflow, model configuration and editing tools produced at least one human-accepted, genuinely complete novel without pervasive generic filler or repetition. Fail when unreviewed AI writing is published, novel completion is misrepresented, or material continuity/filler issues remain.

## Gate 2 — A complete usable audiobook of that same novel

Generate all approved Binder chapters for the **same source edition** with persistent narrator and character assignments. Produce playable complete-length recordings (not only a 10-second demo), allow author-controlled corrections and retakes, and detect stale manuscript/cast edits before final assembly.

Must support: chapter-by-chapter proof listening and explicit acceptance; recorded/audio and manuscript source hashes; no missing, repeated or truncated lines; controlled pause/resume and interruption recovery; consistent voice assignments; final M4B or retailer-supported chapter exports with metadata and valid encoding; local technical checks; rights/licensing review. Confirm the recording matches the accepted novel edition. **No generated audio is implicitly publication-approved.**

Human acceptance is needed for performance, pronunciation, emotional tone, transitions and the entire audio's listenability. Existing Kokoro draft WAV generation is a good start, **not** this gate. Existing SAPI M4B/proof tooling cannot substitute for verified neural-draft proofing and delivery.

## Gate 3 — A clean and safe installation

From a versioned archive on a **fresh supported Windows test environment** with no developer dependencies, a regular user must complete setup and launch through the documented path. The UI must open; create, save, reopen, import and export manuscript projects; and gracefully run with no AI model, GPU, voice model or network connection after installation. Optional large models must not be silently installed when a user requests a lightweight writer-only setup.

Test installation, update and uninstall *without deleting manuscripts*, from standard and space-containing paths, using an absolute custom author-data path. Verify the optional local neural engine can be installed separately and that original data paths and configuration survive upgrade and restart. Installer downloads and license terms must be transparent. The clean test must cover the public Pinokio launcher as well as direct installation before publishing the launcher.

## Evidence must precede promotion

A beta candidate is promoted **only when all three gates pass on the exact source commit/artifact**. A source ZIP built from one commit cannot be certified using tests from a different tree. Preserve the original data directory; never mutate real author projects for testing.

| Gate | 0.15.0 RC1 evidence | Decision |
|---|---|---|
| Novel | Durable local 80-chapter generation path, author approval and editorial tools exist. **No independently read/accepted 60k-word full novel.** | **FAIL / not proven** |
| Audiobook | Short real neural scenes and two very short chapters rendered. SAPI audiobook and M4B support exists. **No full-book neural proof/re-take/approved output.** | **FAIL / incomplete** |
| Install | Fresh RC archive extracted to a separate checkout; Python 3.11 backend and npm frontend installed/built, synthetic project created via live isolated API. The archived `install.ps1` completed using no-model/no-image-download switches. **Still no separate clean Windows machine, author data upgrade, offline first run, or Pinokio launcher verification.** | **PARTIAL** |

Current release status is **private test candidate**. Do not publish or market it as public beta, complete novel-writing proof, or professional-quality neural audiobook production until the documented gates are met.

## Test fixture and record

Use synthetic or explicitly authorized fiction, never real customer manuscripts. Keep a saved QA record containing the release commit/tag, hardware/software versions, model versions, hashes of exported books and audio, chapter/word/duration totals, sampled and full listening findings, author sign-off dates, clean install logs, and unresolved defects. Author sign-off cannot be manufactured by a script.
