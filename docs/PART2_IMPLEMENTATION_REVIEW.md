# Part 2 — Character & Scene Studio: implementation and verification

**Implementation:** `feature/part-2-character-relationship-scene-studio`, stacked on the existing Part 1 branch.
**Status:** Integrated author-review build, not a certified commercial release.

## Why Part 2 exists

Authors should not have to maintain disconnected forms for motivations, relationships, scene beats and continuity. Part 2 connects these through a private, visual creative workspace. Everything that looks like a **fact** is linked to an accepted Series Vault assertion. Everything that looks like a **plan** remains clearly labeled as a draft, never silently added to canon.

Access: **Series → Character & Scene Studio**, with three primary modes.

## 1 · Character Arcs — visual cast + changing psychology

- A scrollable cast portrait gallery with polished editorial cards, selection and search.
- Author-authored descriptions; no fabricated portraits or invented traits.
- Five sourced facets: goals, fears/wounds, values/beliefs, speech signature, secrets.
- Each cited statement displays its exact quotation, source volume and source action.
- Book and within-book point filter exclude future claims. A source-based arc river shows where each character's development appears across books.
- Unestablished facets remain visibly empty, with no automatically synthesized psychology.

**Reality check:** The psychological evolution is an evidence-indexed view. It is not yet a free-form AI psychologist or a full causal motivation simulator.

## 2 · Relationship Orbit — emotional connections with traceable history

- A cinematic constellation of characters and explicitly linked accepted relationship assertions.
- Every pair has a selectable evidence timeline showing trust, distrust, protection, affection, conflict, boundaries and other applicable predicate types.
- Claims are kept directional and scope-specific; one person's feelings do not imply another person's feelings or consent.
- Book/scene scrubbing shows only claims available at the selected point.
- Character nodes can lead into the Character Arcs view. Connection pills are keyboard accessible.
- This can surface opposing states like trust and distrust without hiding them behind an invented single relationship score.

**Reality check:** Trust and intimacy are not converted into arbitrary numerical values. The orbit does not simulate new relationship feelings from raw scene prose.

## 3 · Scene Director — visually plan before prose

- A six-beat starting storyboard: Arrival, Inciting Spark, Obstacle, Reversal, Decision and Aftermath.
- Dramatic tension curve updates from each beat's pressure value.
- Drag-and-drop scene cards, plus independently focusable keyboard reorder buttons.
- Selected-beat inspector changes kind, description, pressure and title.
- Advanced scene intentions drawer for book/scene point, POV, local place, goal, conflict, opening and aftermath.
- Cast choice and voice / relationship / intimacy direction, including author-defined boundaries.
- **Before/After ledger:** the chosen cast's approved source-backed state before the scene, and the author's proposed consequences afterward.
- Explicit **Copy directing brief** action allows the author to paste an authored scene plan into Writer / existing Scene Architect without a cloud dependency.
- Privately persisted, versioned JSON scene boards. Concurrent edits are rejected instead of silently overwritten; save/edit/delete operations are explicit.
- The full private Series Vault backup now includes scene boards. Restoring a series remaps character and location IDs and restores the author's scene drafts independently.

## 4 · Continuity Guardian / preflight

- **Existing scanner:** Inspect a drafted scene description for known entities; optionally compare one explicit author-supplied proposed claim to established canon.
- **New scene preflight:** Read-only checks of staging, physical conditions, carried objects, and relationships for the declared cast at the chosen story position.
- A character whose last approved location differs from the planned scene venue triggers a **travel/staging reminder**, not an assertion that movement is impossible.
- Every preflight reminder cites the exact approved source quote and opens its source in Canon Graph.
- Unapproved and future-book facts are excluded.
- No automatic manuscript modifications, proposed fact approvals, or generated prose insertion.

**Reality check:** This does not prove travel times, physical feasibility, emotional authenticity, or implied consent. The test is grounded in explicit source-backed facts.

## How the pieces connect

```
Series Vault (rights-cleared imported books)
          |
       Canon Graph (source-approved assertions)
          |
    Selected book + scene sequence
          |
 +--------+---------+
 |                  |
Character Arcs   Relationship Orbit
 |                  |
 +--------+---------+
          |
   Scene Director (author-directed beat plan)
          |
   Preflight + Continuity Guardian
          |
  Explicit save / copy brief
          |
 Existing Writer / Scene Architect
```

Scene boards are planning artifacts stored inside the local Series Vault. They do not imply canon changes. Only author-approved sourced assertions influence the factual story views.

## SQLite fix delivered with Part 2

Existing `sqlite3.Connection` used with a `with` statement commits or rolls back without closing the OS file handle. On Windows this left temporary `.ember/story.db` files locked during test teardown. Added `sqlite_lifecycle.ClosingConnection` with explicit closing in its exit path and replaced the seven local project database connection factories that were implicated. Rollback/commit and file deletion are covered by standalone tests.

- Formerly failing Book Jobs and Book Reviews modules: **12/12 passed**.
- Original application suite after SQLite repair: **642 passed, 6 skipped, 0 failed**.
- Full application suite including new Part 2 tests and preflight: **650 passed, 6 skipped, 0 failed** (latest run).
- Part 2 scene board, backup/restore, preflight and lifecycle focused tests passed.
- Frontend TypeScript / Vite production build passed.
- Existing Vite bundle-size and Harper.js browser-externalization warnings remain outside this feature's scope.

## Real browser acceptance

Chrome DevTools Protocol test uses only an explicitly verified local synthetic series `The Astral Lanterns`. It exercised:
- Mode switching among Character Arcs, Relationship Orbit and Scene Director.
- A six-beat board creation, dramatic beat selection and author-initiated save.
- Round-trip API persistence.
- Explicit continuity scan.
- Desktop 1440px, tablet 900px and mobile 390px views with measured page and Studio-container overflow checks.
- Source-backed personal evidence and relationship history.
- Synthetic review board with three selected characters, dramatic goals, consequence and cast-linked source facts.
- All screenshot images below are **actual app captures**. No generated promotional mockups or private manuscripts were used.

### Screenshots

- [Character Arcs desktop](screenshots/part2-synthetic/01-character-arcs-desktop.png)
- [Character psychology evidence detail](screenshots/part2-synthetic/11-character-evidence-details.png)
- [Relationship Orbit desktop](screenshots/part2-synthetic/02-relationship-orbit-desktop.png)
- [Relationship history detail](screenshots/part2-synthetic/12-bond-timeline-details.png)
- [Scene Director](screenshots/part2-synthetic/04-scene-board-desktop.png)
- [Saved Scene Director](screenshots/part2-synthetic/05-scene-saved.png)
- [Beat tension curve](screenshots/part2-synthetic/13-beat-tension-detail.png)
- [Scene direction inspector](screenshots/part2-synthetic/14-scene-director-inspectors.png)
- [Before / After state ledger](screenshots/part2-synthetic/15-before-after-ledger.png)
- [Evidence-backed continuity checks](screenshots/part2-synthetic/16-continuity-guardian-results.png)
- [Mobile Scene Director](screenshots/part2-synthetic/07-scene-mobile.png)
- [Mobile Character Arcs](screenshots/part2-synthetic/08-character-mobile.png)
- [Mobile Relationship Orbit](screenshots/part2-synthetic/09-relationships-mobile.png)
- [Tablet Relationship Orbit](screenshots/part2-synthetic/10-relationships-tablet.png)

## Explicit remaining work / Part 2 completion gates

This branch represents a significant integrated build, not completion of every aspirational feature:
1. Scene plans can be copied as directing briefs, but native one-click *open in Writer* handoff and automatic round-trip manuscript-to-scene synchronization are not yet implemented.
2. Optional author-owned character portraits, image references, local media editing and asset export are not yet implemented.
3. Geography and knowledge consistency are source-backed checks, not a travel-duration engine or a general AI causal/sentiment simulator.
4. Long-form character psychology modeling, relationship transition suggestions and coven/group dynamics beyond explicit cited facts need carefully tested model-assisted author-review workflows.
5. Independent screen reader, high zoom, and large-scale author usability validation remain open.
6. Local Ollama long-form generation is still blocked by Part 1 workstation/model throughput issues and is not marked validated.

**Do not merge as a fully finished public product until the author signs off on the visual experience and these acceptance gates are agreed.**
