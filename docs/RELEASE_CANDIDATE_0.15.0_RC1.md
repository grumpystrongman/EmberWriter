# EmberWriter 0.15.0-rc.1 — author-first release candidate

**Status: local test candidate, not a public GA release.** The RC packages the current novel-writing, planning, editorial, cover, publishing, basic Windows narration, neural voice rehearsals and resumable draft neural audiobook pipeline behind one version checkpoint.

## What this candidate is for

Authors should be able to create or import a real manuscript, edit chapters, navigate the Binder, run optional analyses, revise only with explicit approval, preview publishing artifacts, manage character voices, generate locally rehearsed dialogue, and produce draft neural narration. **Writing must remain available when no AI models, GPU, or speech engine are installed.**

No audiobook recording is automatically proof-approved or retailer-certified. Kokoro neural drafts currently remain separate from the approved SAPI audiobook/export flow. Film-style vocal acting, neural per-line retakes, full author listening approval, advanced audio drama mixing, and production-certified mastering remain future work.

## Test protocol — protected author data

Before testing, **back up existing manuscripts**. Use **a new synthetic/test project first**. Do not uninstall or delete an existing project's data directory to test this version; project storage and model caches are separate from the source checkout.

On the Windows computer, open the release candidate checkout and use the existing `install.ps1` / `start.ps1` scripts. The default setup may install Ollama models and image tools; those downloads can be large and are independent of basic writing. For a lightweight smoke run after dependencies are prepared, the start script supports `-SkipManagedImageEngine`. The optional Kokoro model bundle is not part of the source archive and remains installed separately in `%LOCALAPPDATA%\\EmberWriter\\models\\kokoro`.

### Author acceptance checklist

1. **Write without AI:** create a test novel, rename chapters, edit and save prose, close and reopen, and verify all prose is retained. Try a chapter of at least several thousand words.
2. **Portable author content:** import or create two chapters, then export EPUB/DOCX/PDF; inspect order, navigation, cover, and content rather than trusting a green build.
3. **Editorial autonomy:** run grammar, continuity, and editorial checks, reject suggested edits, then verify the manuscript remains unchanged. Approve one test edit and confirm the recovery/version option exists.
4. **Casting continuity:** create two saved characters with different voices; assign lines in separate chapters; reopen the app and confirm speaker identities and pacing persist.
5. **Audio rehearsal:** use the local Voice Lab to render a short narrator + two-character passage. Listen for clipping, pronunciation, transitions, lost words and awkward speaker changes. Kokoro is a fixed-voice engine, not emotional performance direction or voice cloning.
6. **Neural book draft:** generate two test chapters, pause after a segment, reload the page, and resume. Verify the WAVs play, author approval remains **false**, and the text has not changed.
7. **Change protection:** change a character's voice or a chapter's text after recording. The earlier batch should be flagged stale; it must not silently become a current approved recording.
8. **Release guardrails:** test ISBN/cover/distribution package validation with noncommercial dummy details. Confirm no private documents are included unintentionally.
9. **Recovery:** close/reopen and confirm the project, Binder, voice profiles and draft outputs survive. Keep the test project isolated from real manuscripts.

### Stop-ship criteria

Do not publish publicly if the app overwrites author text without approval; loses project data; mixes incorrect character voices; makes network calls during an explicitly offline neural job; leaks project paths or text; mistakenly reports an unreviewed recording as approved; or fails a clean-machine installation. Any reproducible crash that corrupts Binder/project state is a blocker.

### Verification and limitations

Local pre-tag verification covers the full backend suite, Ruff with a documented **file-specific pre-existing lint baseline**, npm clean install and audit, PowerShell syntax, package audit, compiled modules, hosted frontend build/API URL rewrite, JavaScript chunk budget, and synthetic live API/narration smoke tests. See `docs/LINT_REVIEW.md` for debt still to remove.

**Not yet established:** clean Windows installation on a second machine; Mac/Linux desktop parity; full novel (~100k words) neural endurance; subjective acting/audio quality; retailer acceptance; accessibility certification; production GPU performance across varied devices; actual user acceptance.

## Local release decision

Mark this version **RC / testing** until author acceptance above has passed. Do not issue a GA tag, update the public Pinokio launcher, or claim commercial-audiobook certification from CI alone. The release manager can promote the same tested commit after fixes, documented hardware licensing review, and clean-install verification.
