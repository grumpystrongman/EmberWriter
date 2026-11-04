# Interface quality audit — November 4, 2026

## Scope and evidence

This review examined the actual EmberWriter frontend in an isolated synthetic
project, not the author's private installation or novels. Chrome's local
DevTools protocol captured **16 screenshots** across three viewport widths
(1440, 900, 390 CSS pixels), following four steps at each width:

1. Open **Plan → Write the book → Production guide**.
2. Switch to **Plan → Edit & review → Editorial overview**.
3. Open **Publish → Readiness**.
4. Switch to **Publish → Book files**.
5. Switch to **Publish → Audiobook** to verify narration pacing, readiness control and the compact whole-book action on desktop, laptop and narrow screens.

At 900px, the audit also opens a **26-chapter synthetic editorial corpus**, verifies first-page limit of twelve, loads a second page of twelve, and narrows results to one chapter using a path search. This fifth capture tests scaling to a novel, rather than only testing navigation on an empty project.

The captured PNGs stay on the developer machine under
`frontend/.ux-audit/` and are deliberately ignored by Git. Reproduce with
`npm run ux:visual` from `frontend` after starting a local synthetic-only
test backend and the frontend dev server (and an isolated Chrome browser
exposing DevTools port 9227). The harness **refuses to capture** when the
backend contains anything besides one synthetic-named project. Never turn
off that protection or commit live manuscript screenshots to a public repo.

## Confirmed findings and fixes

| Finding observed | Impact | Change implemented |
|---|---|---|
| **Eleven equally weighted Plan tabs** | Authors could not see the main writing journey | Four task groups, each revealing only one to four relevant tools; default is the guided production flow |
| **Too many top-level workspaces** | Every advanced tool competed with writing | Five primary destinations on desktop, three on narrow screens; the remaining destinations live under an accessible **More** menu, with existing Ctrl/Cmd number shortcuts retained |
| **Global page minimum width of 1,100px** | At 900px, 200px of the page was pushed off-screen; horizontal page scrolling obscured controls | Removed minimum width and verified document overflow at all three test widths |
| **Top bar used three grid columns for four items** | After the More menu was introduced, action buttons wrapped into another row | Corrected grid layout and added narrow-screen layout rules |
| **Publish mounted all tools in one long stack** | Authors faced a wall of unrelated production forms | Six short publishing stages with only the selected tool mounted |
| **Publish was mounted twice in different React trees** | Hidden duplicate component work, duplicate DOM and confusing test results | Removed the redundant old PublishPanel from the legacy editor tree; publishing lives in the dedicated CenterWorkspace |
| **Production conductor hid its first useful action below the fold** | First-time users saw headings and a large checkbox area before they could start | Shortened the introduction, surfaced the model field and primary button, placed optional reader choices behind an expander, and collapsed stage details, chapter ledger and prompt inspection by default |
| **Background reader evaluation could be started without an obvious opt-in** | Extra inference work might surprise the author | Independent reader personas now start **unselected**; the author explicitly enables them |
| **Duplicate floating Import controls** | An orange import action obscured chapter tools and manuscript space | Existing project Library import control is compact; its redundant floating launcher is hidden after opening a project |
| **Performance control obscured mobile content** | Bottom overlay hid action buttons on narrow screens | Reduced mobile performance control to a small, accessible icon |
| **Brand was a clickable div** | Keyboard navigation to Write was unreliable | Replaced it with a native labeled button and visible focus treatment |
| **Whole-book editorial board displayed all chapters and findings at once** | An 80-chapter novel could fill an immense, sluggish screen | Added chapter search, open/all filter, manuscript/priority sort, 12-chapter progressive loading, at most 12 pending findings initially per open chapter, collapsed auxiliary metrics and history, and batch cap messaging |
| **No repeatable responsive regression check** | UI bloat could quietly return in later releases | Added a synthetic-only Chrome layout smoke harness with screenshots and assertions |

## Layout and accessibility checks

The browser smoke test asserts:
- Plan has **exactly four** top-level task groups and **no more than four**
  context-sensitive tool choices visible at once.
- Publish shows **six** clear stages and mounts **one production tool family**
  at a time.
- The currently selected Publish stage is scrolled into view in the horizontal stage navigation, even at 390px; Audiobook exposes pacing, whole-book narration and technical QC without overwhelming the layout.
- Document `scrollWidth` does not exceed viewport width at 1440, 900 or
  390 CSS pixels.
- On a narrow screen, Write, Plan and Publish remain directly accessible;
  other workspace destinations remain reachable in the More menu.
- A synthetic large-book scan initially mounts at most twelve chapter cards, loads another twelve on demand, and narrows the view by chapter path.
- More opens and closes with Escape, the EmberWriter home control is a real
  button, and active destinations expose appropriate ARIA state.

**Accessibility limits:** Captures establish visual layout and browser DOM
state, not WCAG compliance. Real keyboard-only walkthroughs, screen-reader
testing (NVDA/VoiceOver), reduced-motion checks, touch testing, high zoom,
color-contrast instrumentation and long-manuscript stress remain necessary.
The repeated page headings and some older panels still have legacy visual
density. Avoid claiming those are resolved.

## UX release bar going forward

A new feature should not add another top-level workspace or a new permanent
tab just because its backend exists. Prefer task-oriented entry points within
the established groups and show technical internals only when an author opts
to expand them. On the main path, the next author action must be visible in
the first viewport. Check at 1440, 900 and 390 pixels, keep actions keyboard
reachable, and ensure hidden tools are **unmounted**, not merely hidden with
CSS while still fetching data.

The UI pass does not change the author-led safety contract: model critique is
optional, corrections require review, and publishing needs explicit action.
