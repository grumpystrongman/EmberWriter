# Stage 3/4 qualification hardening — November 16, 2026

## Scope and honesty

This is an engineering increment, **not** a claim that Stage 3 or Stage 4 has passed. Stable release remains blocked until all 38 scorecard gates independently earn 5/5 on the same shipping commit with real author and expert signoffs. All work is isolated in `stage2-chunk18-certification` and does not modify the main development checkout.

## Verified work

- The Stage 3 workflow backend contract checks passed: `py -3.14 -m pytest backend/tests/test_book_revisions.py backend/tests/test_project_recovery.py backend/tests/test_scene_generation_contract.py -q` — **42 passed**.
- The production frontend compiled: `npm run build` (TypeScript + Vite), exit 0. Note Vite's harper.js browser-external `fs` warning; this is not a browser-runtime acceptance test.
- The release scorecard verifier now rejects invalid/malformed JSON objects with a deliberate release-hold message, guards non-array gate inventories, rejects absolute/escaped receipt paths and symlink targets outside the allowed evidence directory, and rejects invalid or future human-review dates.
- `node --test scripts/test_release_scorecard.mjs` — **7 passed**, including new negative-path checks. `git diff --check` completed without errors.
- The Stage 2 plan now permits optional independent public-web corroboration for documented published facts, without replacing manuscript-grounded answers or independent author review.

## Outstanding Stage 3 exit evidence

Real interactive tests must still demonstrate the complete Plan/Analyze → Writer → Revision journey, navigation/selection preservation, selected-edit undo, cancellation and failed-generation recovery, editor focus/keyboard usage, context-aware help, offline-help steps, and 390/900/1440px + 200–400% zoom accessibility. No claim of full usability certification from backend contracts alone.

## Outstanding Stage 4 exit evidence

Requires exact-commit full-suite receipts, crash/low-disk/concurrent-edit stress, NTFS backup/restore and clean-install/update/uninstall drills, large-series throughput with real local models, WCAG 2.2 AA/NVDA testing, EPUBCheck/reader/print proofs, threat-model review, independent novelist user testing, and 38/38 human + machine evidence in the protected release manifest. No fabricated human attestation or auto-5/5 from public internet matches.

## Next qualification action

Run live isolated synthetic-project browser acceptance, gather exact-commit Windows install/export/restore evidence, and collect external author/expert reviews. Preserve private books and labels locally; do not place them into Git or public tooling.

## Subsequent implementation and verification

- Stage 3 Revision Workbench now offers **Stop waiting for proposal** and **Refresh revision history** controls, separates client wait cancellation from server-side generation, and aborts outstanding proposal fetches on workspace/chapter switching. The UI explicitly warns that a server-side local job may still finish after the client stops waiting. This avoids falsely claiming the underlying model was canceled.
- Full local Python backend run: **934 passed, 2 skipped, 1 warning** in 206.55 seconds. The warning is an intentional duplicate EPUB mimetype adversarial test fixture. Two skips remain; a full 5/5 qualification must review skipped-critical cases separately.
- After Revision Workbench changes, TypeScript + Vite production build succeeded (`npm run build`).
- Windows installation/launch PowerShell scripts passed `scripts/validate-powershell.ps1` syntax validation.
- `npm audit --audit-level=moderate` exited 0.
- Ruff initially found five style violations, corrected in pronunciation lexicon and two backend tests; `py -3.14 -m ruff check backend/app backend/tests` then passed.

This is automated engineering evidence only. The Stage 3 browser journey, screen-reader accessibility and real author review, and Stage 4 clean Windows install/migration/recovery, device publishing proofs, and all 38 independent signoffs remain required.

## Live browser qualification and security follow-up

- Using the local Chromium debugger and a synthetic editorial project, the Release Lab audit passed: 38 quality gates, 5 domains, no false certified scores, visible proof inspector, responsive 1440px/390px layouts. Private and real manuscript contents were not written to Git.
- Fourteen author UX screenshots were captured at mobile, tablet and desktop widths. They are retained in a private local evidence directory, not the repository. Automated DOM probes reported potentially unnamed and small controls; these require accessibility review and cannot be counted as WCAG/NVDA signoff.
- The live author UX interaction script passed mobile workspace navigation, offline help, and series navigation checks. Its complete scene handoff remains **not verified** because no saved synthetic scene-board fixture was present. The script's outdated expectation of four series tabs was corrected to five, including Knowledge Lab. No private or real-series board was modified just to satisfy the test.
- SonarCloud PR 166 initially failed the new-security rating due to arbitrary CLI manifest path handling and PATH invocation in tests. The release verifier now accepts only the fixed checkout path `release/quality-evidence.json`, forbidding arbitrary CLI file reads; tests derive checkout identity from local Git metadata without launching Git from PATH. Eight targeted certification tests passed locally after the correction. A new remote Sonar scan is required before calling this gate green.

## Isolated scene-workflow diagnosis

- The author UX script now chooses the known synthetic series **The Astral Lanterns** explicitly, rather than accidentally inspecting the first series (the private Destroyer continuity lab). The synthetic series has two saved boards, but the live UI refused to load its selected detail with `Source snapshot checksum mismatch`. This is a genuine fixture-integrity blocker, not a missing feature or authorization to alter the source checksum.
- Fixed `SeriesDesk` to clear previous-series data immediately on a selection change and ignore out-of-order responses from older selections. If the new source cannot pass integrity checks, its error remains visible instead of leaving stale prior-series data on screen. This is especially important when users switch between private source libraries.
- The frontend TypeScript + production Vite rebuild passed after that change. Full Scene Director to Writer handoff remains blocked on a clean synthetic source fixture; no real-series content was modified, and no checksum was bypassed.
