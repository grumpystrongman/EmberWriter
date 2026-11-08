# EmberWriter release qualification: completed engineering verification

**Date:** November 7, 2026  
**Candidate:** `feature/release-qualification-gates` — draft [EmberWriter PR #127](https://github.com/grumpystrongman/EmberWriter/pull/127), stacked above #126  
**Distribution:** Existing [EmberWriter-Pinokio](https://github.com/grumpystrongman/EmberWriter-Pinokio) launcher, draft [PR #2](https://github.com/grumpystrongman/EmberWriter-Pinokio/pull/2)

## Defects discovered and resolved

1. **Backup/recovery manuscript fingerprint mismatch on Windows.** Files opened as text had CRLF normalization whereas saved bytes used platform-dependent newlines. Manuscript atomic writes now use `newline="\n"` explicitly, and the 20-chapter backup/mirror/recovery test verifies exact original SHA-256 bytes. A permanent test asserts LF data is written byte-for-byte rather than implicitly converted.
2. **False failure in clean Windows installation acceptance.** Windows PowerShell interpreted non-fatal pip/npm stderr messages as terminating errors, while process-object exit code reporting was unreliable. The QA harness now captures stdout and stderr separately with the native `$LASTEXITCODE` and stops on actual installation failure. The isolated clean-archive test completed, including a second installation without manuscript changes.
3. **Hosted Pinokio frontend could talk to the wrong local API.** The Vite API rewrite matched POSIX `/src/` paths, but Windows plugin identifiers sometimes contained `\\src\\`. Normalize path separators before matching. Production builds with `VITE_API_BASE_URL=/api` now contain **no** literal `http://127.0.0.1:8000/api`, and real Edge browser testing checks that every API request stays on the current Pinokio workspace origin.
4. **First-run UI acceptance script assumed a selected series already existed.** It now waits for asynchronous Series Vault hydration and creates a *synthetic* series through the actual first-run UI when necessary. No pre-existing author-series data is touched.

## Latest verified automated tests

| Gate | Result | Notes |
|---|---|---|
| Full backend pytest | **623 passed, 2 skipped** | 241.37 seconds, Windows scratch checkout |
| Python static analysis | **Passed** | Ruff including application, tests and release qualification scripts |
| Hosted frontend TypeScript + Vite | **Passed** | Explicit `VITE_API_BASE_URL=/api` |
| Large synthetic novel | **Passed** | 20 chapters, 60k+ words, explicit approval, EPUB/DOCX roundtrip |
| Synthetic audiobook production contract | **Passed** | 20 chapters, checksums, stale-audio detection and author approval boundary; waveform generator mocked here |
| Real neural audiobook synthesis | **Passed separately** | 20 short synthetic chapters, actual local Kokoro ONNX CPU speech, 203 seconds audible waveform, source integrity |
| Multi-volume backup, mirror, restore | **Passed** | Byte-identical author text and media, old edition recoverable, current edition left untouched |
| Clean-archive Windows writer-only install | **Passed** | Install with no optional models; create/save/reopen; EPUB/DOCX; backup verify/restore; repeat install preserves bytes |
| Dedicated Pinokio launcher tests | **Passed** | 7 tests, 1 skipped; deployment 2 passed; JS menu passed |
| Live dual-server Pinokio integration | **Passed** | Scratch loopback private/demo mode; no private book leakage; backups verified |
| Hosted browser UI | **Passed** | Edge 1600×900 and 390×844, no JS/API errors, overflow, floating-control overlap or cross-origin API requests |

The **two main-suite skips** are (a) OS symlink-creation privilege missing for that Windows account — a separate NTFS junction escape regression passed — and (b) the opt-in full neural integration check, which was invoked separately with the actual installed Kokoro ONNX model and passed. The dedicated launcher had one Windows NTFS-specific skip on a runner without junction permission; regular backup protection is separately verified.

The source code and test data remained in isolated QA checkouts; no real author manuscripts or the production source repository were overwritten. Test servers were stopped after use.

## Public release remains intentionally blocked

Green automated engineering tests are **not** equivalent to an author-approved publication. The protected qualification script `scripts/qualify_release.py` explicitly fails when these independent release criteria are missing:

- Complete 60k+ word novel generated/written, read and individually approved **by a real author** and reviewed by a real human editor. Synthetic prose does not qualify as artistic acceptance.
- An actual, complete accompanying audiobook proof-listened by a human with no major unresolved dialogue, cast, pacing or pronunciation defects. Twenty short synthetic neural chapters demonstrate the engine but **not** four hours of finished audiobook acceptance.
- A truly fresh supported Windows OS install using **the real Pinokio application's graphical install/update interface** (not just its scripts), and safe uninstall/reinstall and recovery from independent encrypted storage.
- Final author rights, attribution, model usage and release-owner signoff.
- Stacked source changes merged in dependency order and the dedicated distribution repo tested against that exact merged release commit.

Do not publish the new **application** release or claim universal zero-loss protection until these are independently completed. The already-public **10-minute demonstration video** is separate and remains available.

## Repeatable gates added

The main repository now includes a Windows CI release-safety job: large synthetic novels, NTFS recovery, release-manifest checks, hosted Vite same-origin build and actual clean-archive Windows install. The dedicated Pinokio repository has its own Windows launcher safety workflow and a synthetic hosted UI/dual-server test.

**Current engineering disposition: ready for controlled human release acceptance, not yet signed off for general publication.**
