# Release Candidate Lint Review — bounded exceptions

The CI lint gate is kept enabled. This ledger scopes pre-existing warnings to exact files, not entire rule families. These are **open quality tasks**, not evidence of complete remediation. Each exception must be retired after code-specific review, without changing API error contracts or crash-recovery behavior.

Current baseline: **38 file/rule pairs**. The original full-check report contained 45 findings; some file/rule pairs cover multiple instances.

| File | Allowed finding codes | Release-review rationale |
|---|---|---|
| `app/atlas_hierarchy.py` | B023, F401 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `app/audio_production.py` | TRY004 | Input validation exception compatibility with existing route and test contracts. |
| `app/audiobook_jobs.py` | BLE001, S110 | Background job, cancellation and recovery paths need deliberate exception handling. |
| `app/audiobook_local.py` | TRY004 | Input validation exception compatibility with existing route and test contracts. |
| `app/autopilot.py` | TRY004 | Input validation exception compatibility with existing route and test contracts. |
| `app/book_jobs.py` | BLE001, S110 | Background job, cancellation and recovery paths need deliberate exception handling. |
| `app/book_reviews.py` | TRY004 | Input validation exception compatibility with existing route and test contracts. |
| `app/book_revisions.py` | TRY004 | Input validation exception compatibility with existing route and test contracts. |
| `app/book_studio.py` | TRY004 | Input validation exception compatibility with existing route and test contracts. |
| `app/continuity_audit.py` | SIM102 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `app/editorial_board.py` | RUF059, TRY004 | Input validation exception compatibility with existing route and test contracts. |
| `app/editorial_pipeline.py` | BLE001 | Background job, cancellation and recovery paths need deliberate exception handling. |
| `app/generation_reliability.py` | PLC0414 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `app/local_resources.py` | SIM115 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `app/m4b_jobs.py` | BLE001, S110 | Background job, cancellation and recovery paths need deliberate exception handling. |
| `app/production_conductor.py` | BLE001, S110 | Background job, cancellation and recovery paths need deliberate exception handling. |
| `app/production_preflight.py` | FLY002 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `app/proof_approval.py` | TRY004 | Input validation exception compatibility with existing route and test contracts. |
| `app/prose_editor.py` | SIM102 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `app/routes_generation.py` | BLE001 | Background job, cancellation and recovery paths need deliberate exception handling. |
| `app/routes_manuscript_intelligence.py` | B008 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `app/story_arc_investigator.py` | ISC004, TRY004 | Input validation exception compatibility with existing route and test contracts. |
| `app/style_bible.py` | TRY004 | Input validation exception compatibility with existing route and test contracts. |
| `app/voiceprint_lab.py` | TRY004 | Input validation exception compatibility with existing route and test contracts. |
| `tests/test_audiobook_quality.py` | ASYNC221 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `tests/test_book_reviews.py` | SIM117 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `tests/test_book_revisions.py` | SIM117 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `tests/test_continuity_audit.py` | SIM117 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `tests/test_explicitness_enforcement.py` | I001 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `tests/test_release_proof_cast_noise.py` | SIM117 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |
| `tests/test_story_arc_investigator.py` | SIM117 | Preexisting narrowly scoped style/refactor/async-test finding; no functional change accepted without regression tests. |

Release must still pass: full backend tests, frontend build and JS chunk budget, dependency audits, live synthetic startup checks and manual author-workflow QA. No claim of zero technical debt is made.
