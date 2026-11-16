# EmberWriter 0.16.0 RC1 — Stage 3/4 technical preview

**Distribution:** public GitHub prerelease and Pinokio launcher update. **Not GA or independently 5/5-certified.**

This release candidate integrates Stage 2 series/evidence intelligence with Stage 3 editorial workflows and Stage 4 release-safety hardening. It is suitable for author testing on a separate backed-up library. It is **not** retailer-approved and does not automatically approve or publish manuscripts, generated scenes, or audiobooks.

## What's new
- Series continuity evidence search, reviewed claims, cross-volume semantic context, narrative timeline and author-controlled research proposals. Source and canon changes remain explicit.
- Scene Director saved storyboard → confirmation → Scene Writer handoff; reviewable revision proposals with safe stop-waiting and refresh-history controls.
- Cross-series state isolation: failed loads cannot leave data from a previously selected series visible.
- Enhanced release evidence validation, strict hash/path integrity, and 3 synthetic disk-full atomic write recovery tests.
- Improved Studio selectors, mode button semantics, typography contrast, and floating control placement.

## Verification snapshot
- Full local backend regression prior to final UI-only edits: **934 passed, 2 skipped**. Targeted disk-failure tests: **3 passed**.
- Local isolated synthetic Chromium workflow: **7/7 interactions passed**, including saved storyboard → Writer prompt without changing manuscript.
- axe-core WCAG-tagged synthetic browser checks: **0 automatic violations** across 6 workspaces at 390, 900 and 1440 pixels (18 views), with no horizontal overflow.
- Latest candidate-source CI must pass: backend, frontend, Studio contract, Windows same-host install/restore, and SonarCloud. See GitHub Actions for the exact shipping commit.

## Install or update
- **GitHub:** use the source archive attached to this prerelease or clone the public application repository.
- **Pinokio (Windows x64):** install the companion launcher from https://github.com/grumpystrongman/EmberWriter-Pinokio and choose **Install**; existing users should back up their library and choose **Update** while no writer or model process is running. Demo and Private libraries remain separate.
- A compatible Python 3.11 runtime, Node/npm and other local tooling are provisioned by the launcher; optional models are separate downloads.

## Known incomplete qualifications (technical deltas)
- A complete browser-level accept/reject/undo revision journey and real installed-model literary evaluation are still pending.
- Independent NVDA, keyboard-only and 200%/400% zoom tests; newly provisioned Windows 10/11 and Pinokio GUI install/upgrade/rollback/uninstall; real concurrent editing and physical low-disk/crash scenarios.
- EPUBCheck/Kindle/Kobo/print proofing, full privacy/threat-model review and 250K–500K word performance runs on stated hardware.
- Independent author and expert signoffs have been deferred by the project owner, **not represented as passed**. The stable release policy remains a strict 38/38 exact-commit 5/5 gate.

## Privacy and rollback
Keep your books local. No licensed reference-book text, private manuscript or model credentials is included in these source archives. Before updating, back up the Private library. Use the previous RC2 prerelease archive/commit if rollback is required; **never replace** existing project data with a synthetic demo or extracted source checkout.

**Reference:** [Stage 3/4 Engineering Delta Register](docs/reviews/2026-11-16-stage34-engineering-deltas.md).
