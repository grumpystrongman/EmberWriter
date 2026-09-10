# EmberWriter Submission & Professional Review Acceptance

This gate supplements `REAL_MANUSCRIPT_ACCEPTANCE.md`. It must be run with an actual author-owned manuscript and at least one real current agent, publisher, editor, or contest guideline page. Placeholder prose and made-up destinations are not sufficient release evidence.

## 1. Source-anchored review comments

1. Open a real manuscript chapter and save it.
2. Select a distinctive passage and create each supported review type at least once: Comment, Question, Issue, To-do, and Praise.
3. Restart EmberWriter and confirm the comments remain attached to the same project/document.
4. Insert prose before one anchored passage without changing the passage itself. Reopen the document and verify Ember re-anchors the comment to the moved text rather than the old offset.
5. Rewrite or delete another anchored passage. Verify the corresponding comment becomes visibly **stale** instead of attaching to unrelated prose.
6. Resolve a comment, hide resolved comments, show it again, reopen it, dismiss it, and delete a disposable comment.
7. Create a named whole-project checkpoint, change `review/annotations.json`, restore the checkpoint, and confirm the review state rolls back with the project text state.
8. Verify review annotations never appear in compiled DOCX, EPUB, PDF, submission samples, or retailer release files.

## 2. Submission destination profiles

Use at least two real destinations whose instructions differ materially, for example one that requires pasted pages and another that accepts attachments.

For each destination:

1. Save its name, contact, submission method, current authoritative guidelines URL, submission URL/email as applicable, sample rule, attachment/body rule, required query/synopsis/bio fields, accepted formats, simultaneous-submission rule if stated, response window if stated, and exact free-form notes needed to follow the published instructions.
2. Close and reopen EmberWriter and verify the destination requirements persist in `publishing/submission-profile.json`.
3. Confirm changing one destination does not mutate another destination's requirements or historical submission records.
4. Re-open the saved guideline URL immediately before a real submission. The current destination instructions override every Ember preset or previously saved note.

## 3. Manuscript-format presets

Test both implemented presets against a real sample:

- **Modern standard novel**: 8.5×11 manuscript page, one-inch margins, 12-point Times New Roman, double-spaced body, half-inch first-line indent, author/title/page header.
- **Shunn-style classic**: same core manuscript geometry with 12-point Courier New / monospaced treatment and the Shunn-style manuscript conventions Ember implements.

Open the generated DOCX in a full word processor and the generated PDF in an independent PDF reader. Do not accept the file based only on its extension or successful generation.

For a full-manuscript handoff, confirm the title/contact page, Binder order, chapter boundaries, paragraph indentation, line spacing, italics/emphasis, scene breaks, header, and page numbering.

## 4. First-page, chapter, word, and full-manuscript samples

For a real manuscript destination, exercise all four sample strategies even if the destination itself uses only one:

1. **Pages**: request a small N-page sample and confirm the generated standardized PDF contains exactly N pages (or all available pages when the manuscript is shorter). Compare the page-N cutoff visually to the full standardized submission PDF. Remember that the convenience DOCX may repaginate in another word processor; the deterministic page boundary is the standardized PDF.
2. **Chapters**: verify the first N compile-enabled Binder documents are selected, in Binder order.
3. **Words**: verify the sample stops at the requested approximate first-N-word boundary without silently skipping earlier manuscript material.
4. **Full**: verify the complete compile-enabled manuscript is present and no Research/Story Bible/non-compile Binder material is included.

## 5. Query, pitch, synopsis, and bio drafting

Use the configured real model endpoint.

1. Build current Story Memory across the manuscript, then draft a query and synopsis. Confirm Ember reports that current story summaries were used.
2. Change a material story fact or ending without refreshing that chapter's Story Memory. Draft again and confirm Ember does **not** use the stale chapter summary. The new manuscript excerpt/current information must supersede it.
3. Inspect the query for title, genre, word count, protagonist, conflict, stakes, and supplied comps. Reject any invented personalization, awards, publishing credits, credentials, representation history, or comp titles.
4. Inspect the synopsis against the actual full novel. It must reveal the ending and major causal turns rather than substituting vague jacket copy.
5. Inspect the author bio. It may polish supplied facts but must not invent occupations, memberships, locations, awards, publications, or expertise.
6. Test a manuscript with more than 40 Binder documents. Confirm fallback context sampling represents both the beginning and ending rather than silently reading only the first portion of a long novel.

## 6. Submission handoff package

For each real destination:

1. Intentionally omit one required material and confirm validation blocks package creation.
2. Restore the material and build the package.
3. Inspect the ZIP outside Ember. Confirm it contains the appropriate query/synopsis/bio/sample/body files for that destination, `destination.json`, `submission-manifest.json`, and `README.txt`.
4. Recalculate at least one SHA-256 checksum and compare it to the manifest.
5. Confirm a page-sample destination receives the exact standardized PDF page sample, while a chapter/word/full destination receives the expected Binder-derived manuscript content.
6. Confirm the package is a handoff only: Ember must not claim it submitted, emailed, uploaded, or received acknowledgement from the destination.

## 7. Submission tracking

1. Build a package and confirm its record begins in **ready** status with no fabricated sent date.
2. Mark the record **sent** with the real submission date. If a response window is saved, confirm Ember calculates the follow-up date from the sent date, not the package-build date.
3. Exercise Partial Requested, Full Requested, Revision Requested, Offer, Pass, and Withdrawn states with disposable records.
4. Record a response date and notes, restart Ember, and confirm the history persists.
5. Build another package for the same destination and confirm the older package ID/history remains intact.
6. Create and restore a whole-project checkpoint and verify the submission profile/tracking history rolls back with the rest of the project-owned text state.

## Release gate

Do not call Submission & Professional Review Studio production-ready until:

- backend tests and Ruff are green;
- frontend TypeScript/Vite production build is green;
- the exact final PR head is green in GitHub Actions;
- a real manuscript has passed the review-comment acceptance flow;
- at least two materially different real submission guideline sets have passed package inspection;
- generated DOCX/PDF submission samples have been opened and visually inspected outside Ember;
- AI-drafted query/synopsis materials have been manually checked against the real manuscript for hallucinated facts or credentials.
