# Stage 2 · Chunk 7: Review queue UX (2026-11-14)

## Problem

Previous panels displayed one large, fully expanded card for each candidate. For 80 source books, 896 potential names, several hundred dialogue clues per volume, and durable extraction plans, a card stack forces excessive scrolling, repeated action bars, and loss of review position. It also burdens phones and narrower sidebars.

## Commercial-product reference patterns

This is UX inspiration from published documentation, not copied application UI or source code:

| Reference | Verified pattern | EmberWriter decision |
|---|---|---|
| Linear issue queues | Dense lists, filters, highlight/selection, J/K or arrow-key navigation, bulk selection when appropriate | Dense list and J/K / arrow navigation. **No bulk canon approvals**, because every claim needs its own evidence. [Linear documentation](https://linear.app/docs/select-issues) |
| Notion databases | Table/list rows open in a right-hand side peek; views can filter/sort/group | Persistent source/evidence pane at right, and one-column stacked behavior in narrow containers. [Notion documentation](https://www.notion.com/help/views-filters-and-sorts) |
| Airtable grid and record review | Scan records in a grid or list, open full record details, filter/sort/group data | Separate compact row summaries from review details. [Airtable grid](https://support.airtable.com/articles/7905594155-airtable-grid-view), [Record review](https://support.airtable.com/articles/4384405105-Airtable-interface-layout%3A-Record-review) |
| ClickUp list | Multi-select with bulk toolbar for repeatable workflow work | Deliberately **not** implemented for speaker/chronology approval; potential future use only for reversible/noncanonical filtering. [ClickUp documentation](https://help.clickup.com/hc/en-us/articles/6309768265495-Manage-tasks-with-the-Bulk-Action-Toolbar) |

## Implementation

The new reusable `frontend/src/ReviewQueue.tsx` renders a dense list, optional metadata/status column, local search on loaded rows, status filter, source/title/status sorting, compact/comfortable density toggle, item count, keyboard J/K and arrow movement when focus is in the list, and a persistent detail inspector on desktop. CSS container queries stack the list/details inside narrow panels independently of the viewport size. The CSS is scoped to `review-queue-*`; no new dependency, cloud service or stored manuscript content is required.

Adopted in four operational surfaces:

1. **Character Minds → candidate names**: ~60 compact rows and original excerpt/author registration in the detail inspector, plus full-corpus server-side name search (still read-only unless the author registers a character).
2. **Character Minds → dialogue / POV**: compact 40-row server pages and separate source-clue vs review-queue tabs, with original quote, speech cue, and deliberate speaker/POV decision in the inspector. No automatic speaker or POV approval.
3. **Story History / Discover → event leads and staged reviews**: compact 80-row server pages and separate original-context inspector. Author event decision ledger starts collapsed, rather than adding a second vertical tower of cards.
4. **Verify → saved model extraction plans**: select persisted batches from compact list rows; progress and one-window/three-window/pause/resume/cancel operations appear only in the inspector. The backend's source hashes, per-window lease, manual stepping, and no-auto-canon guarantees are unchanged.

The app is designed for large loaded result sets without rendering all expanded descriptions. The services already paginate event/dialogue results. The name-candidate scan currently returns the top 60 by default, but server-side search covers all matching candidates. Extraction list is limited to 20 persisted plans. A later release could add richer saved filters and authenticated multi-user assignment if needed.

## Safety and usability constraints

- All approval buttons continue to require individual author review and original source evidence. None of the queue refactoring changes backend data, auto-promotes facts, or transfers source text remotely.
- Filtering is explicitly labeled **Find in loaded rows**; it does not falsely imply searching unloaded pages. Full-corpus search is a separate explicit action.
- Buttons have real labels and focus-visible states. Mobile and narrow workspace layouts reveal the inspector when a row is clicked. When a filter changes the selected visible row, the decision form is rebound to that exact record, avoiding stale author selections.
- Actual Chrome measurement: compact rows **52px** and comfortable rows **96.2px** for the sampled 80-book candidate list. A 390px simulated viewport rendered a **334px** queue with a visible stacked inspector and no queue overrun.
- No bulk approval of speculative events, quoted dialogue, alleged relationships, or identity.
- All original section indexes, source snapshots, event reviews, and dialogue approvals remain in place; this is a UI-only update.

## Verification

- TypeScript/Vite production build.
- Full Series Python regression suite (180 tests at last baseline).
- Browser CDP smoke for actual 80-book Destroyer and four-book reference series: candidate row/quote inspector, dialogue row/quote inspector, exact event excerpt verification, staged event ledger, saved extraction plan/controls, original EPUB recovery affordances and previous views. Checks desktop no-horizontal-overflow, J/K/arrow keyboard movement, compact-vs-comfortable density, and 390px narrow container inspector behavior.
- No commit of private publication excerpts.

## Future follow-ups

The next meaningful narrative milestone remains author-grounded scene segmentation and POV/voice evaluation, followed by multi-book belief-state continuity. The new queue layout is reusable for these review workflows without more blocky card stacks.
