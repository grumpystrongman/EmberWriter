# Author Experience Review System

This folder houses fresh, evidence-backed reviews from the **Author Experience Reviewer** custom agent.

## Invocation

In an agent-capable GitHub Copilot workspace, select `.github/agents/author-experience-reviewer.agent.md` and ask:

> Audit the current EmberWriter UI as a principal product designer and experienced working novelist. Capture the synthetic app, inspect screenshots, score real author tasks, and propose ranked changes with acceptance tests.

## Evidence capture

With the isolated local synthetic demo running at backend `127.0.0.1:8000`, Vite `127.0.0.1:5173`, and Chrome remote debugging `127.0.0.1:9227`:

```bash
node scripts/author_ux_capture.mjs
```

The capture refuses to proceed unless the backend exposes **exactly one synthetic editorial project**. It does not write, delete, upload or approve manuscript content. It records screenshots and a JSON observation file to this directory. It intentionally uses no external generation or analytics services.

The visual evidence **must be inspected before writing review findings**. Screenshot text, keyboard flows and WCAG cannot be fully verified by the screenshot script; the agent must mark those checks as limitations rather than inventing them.

## Review catalog

- [2026-11-12 — Initial author/UX expert audit](2026-11-12-author-ux-review.md): 14 new browser screenshots; current creative flow, information architecture, mobile access, author-trust assessment, and 10 prioritized recommendations.

## How a review becomes a change

1. Validate finding against source, screenshot and actual user journey.
2. Open a numbered GitHub issue with a severity, affected files, measurable acceptance criteria and screenshot reference.
3. Build on a feature branch after product-owner review, preserving author safety and local-first guarantees.
4. Re-run the **same journey** and collect new before/after evidence.
5. Do not call a finding resolved until the exact case and accessibility behavior have been checked.

An installed custom agent is invoked deliberately. It does not run unattended, install an unknown model, or assume authorization to publish.
