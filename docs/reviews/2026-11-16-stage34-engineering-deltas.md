# Stage 3 / Stage 4 — Engineering Delta Register
**Prepared:** November 16, 2026  
**Scope:** Stage 3 author workflow and Stage 4 technical release evidence. Independent author/expert approval is **deferred from the engineering to-do list** at the product owner's request; it is NOT fabricated, waived in the release policy, or treated as a 5/5 signoff.

## Verified automated engineering work
- **Author interface:** 7/7 local Chromium interaction checks passed using an independently seeded, disposable synthetic library. Covered mobile Plan/Series/Publish and More navigation, offline Ember guide progression, series Verify navigation and saved Storyboard → explicit confirmation → Scene Writer prompt, without manuscript overwrite.
- **Accessibility automated audit:** axe-core 4.10.3, 6 workspaces (Write, Plan, Analyze, Publish, Series, Studio) × 390/900/1440px = **18 checks, 0 WCAG-tagged axe violations and no horizontal page overflow** after fixing 27 originally reported rule violations. This does NOT prove manual WCAG AA conformance or screen-reader operation.
- **Release safety:** existing certification verifier continues to block missing/nonconforming manifests; fixed-path release evidence, hash checks and distinct author/expert attestations remain enforced. Eight local release-verifier tests passed.
- **Backend:** earlier same-branch full local regression **934 passed, 2 skipped, 1 warning**. The warning came from an adversarial duplicate-EPUB-mimetype fixture. No full retest after the newest *frontend-only* accessibility changes was needed to validate that UI diff, but the shipping commit still requires exact-commit CI.
- **Build/security:** local TypeScript/Vite build and Ruff pass; npm audit had no moderate-or-higher vulnerability findings. PR #166 previously had green backend, frontend, Studio contract, SonarCloud and Windows manuscript/recovery/install CI checks before this latest set of accessibility changes.
- **Source integrity:** the older synthetic Astral Lanterns dataset failed an immutable snapshot checksum; no checksum bypass or private source mutation was made. A fresh isolated synthetic series with a verified checksum and scene board passed the original blocked browser handoff check.

## Remaining executable engineering / external test deltas
1. **Stage 3 complete novelist journey:** browser-test selected-text edit → preview/diff → accept/reject → undo/revert, failure and cancellation, caret preservation, reopening/restart and concurrent edits. Existing backend contracts are not a substitute for on-screen end-to-end verification.
2. **Stage 3 real local-model output:** repeat full scene generation, source-grounding, paragraph/word count and fallback/timeout behaviors with installed local models. Mock generation and prompt handoff alone cannot demonstrate literary quality.
3. **Accessibility manual + zoom:** keyboard-only focus order, NVDA screen reader, reduced motion, full 200%/400% browser zoom and touch target interaction; automated axe 18/18 is a strong baseline, not the final accessibility qualification.
4. **Stage 4 fresh operating system:** clean Windows 10/11 physical or virtual machine install, offline operation, upgrade/rollback/uninstall, file association and optional Pinokio launcher path. Current Windows CI runs same-host archive QA and intentionally does not certify a freshly provisioned OS.
5. **Stage 4 heavy failure scenarios:** crash mid-write, deliberate low-disk, parallel windows, simultaneous revision conflict and byte-identical backup/restore under load; 250–500K-word performance traces and real-model throughput/latency.
6. **Publishing and delivery:** EPUBCheck, EPUB navigation/accessibility, Kindle/Kobo or equivalent reader proofs, DOCX/PDF/print pagination and external retailer compliance on non-submitted test artifacts.
7. **Privacy and security:** finalized threat model, outbound network inspection, permissions and recovery/secure-erasure audit.
8. **Release policy (deferred):** 38/38 exact-release-commit evidence receipts and independent experienced author/expert reviews. The engineering work may be considered ready for further review without those reviews; the stable 5/5 release must remain locked until they exist.

## Reproducibility and safety
- Source checkout: `stage2-chunk18-certification`, PR #166.
- Fixture script: `scripts/seed_stage34_synthetic.py`; refuses normal author data directories or existing populated QA folders.
- Chromium acceptance script: `scripts/author_ux_verify.mjs`, configured by `EMBER_QA_BACKEND`, `EMBER_QA_FRONTEND`, `EMBER_QA_DEBUGGER`, `EMBER_QA_SCREENSHOT_DIR`, and `EMBER_QA_RESULT_FILE`.
- axe audit script: `scripts/stage34_accessibility_audit.mjs`, configured by the same 3 endpoint variables plus `EMBER_QA_AXE_PATH` and `EMBER_QA_A11Y_RESULT`.
- Full local synthetic screenshots, audit JSON and fixture data remain outside Git in `EmberWriter-Stage34-LocalEvidence`. Do not upload licensed/private manuscripts or excerpts.
- Neither these test harnesses nor a public-web answer match is permission to mark any release gate 5/5 automatically.
