# Stage 2 scene intelligence review

The unchanged 12-case synthetic fixture hash is `9597e288b15a4b8ece1b2ab1036b63ad82d5b21dbe18be813a39f110dc8194d3`. Both measurements were run locally. The original diagnostic scored navigation window splits; the revised diagnostic scores the separate scene suggestion function, so the comparison measures the change in candidate behavior, not an identical prediction interface.

| Measure | Before | After |
| --- | ---: | ---: |
| Boundary true positives / false positives / false negatives / true negatives | 4 / 2 / 4 / 2 | 6 / 0 / 2 / 4 |
| Precision / recall / F1 | 0.6667 / 0.5000 / 0.5714 | 1.0000 / 0.7500 / 0.8571 |
| POV coverage / correct / incorrect | 0 / 0 / 0 | 1 / 1 / 0 |
| Character knowledge coverage / correct / incorrect | 0 / 0 / 0 | 0 / 0 / 0 |

Suggestions are local heuristics based on typographic separators, explicit elapsed-time expressions, and repeated unquoted first-person terms. Offsets identify the literal cue, not proof of a narrative interpretation. A separator following a colon is suppressed as possible displayed material; this can also suppress real transitions. A divider or temporal phrase can still be decorative, quoted, hypothetical, or a flashback within a scene. The POV heuristic can misread quoted speech, letters, or mixed voice; it does not identify a character. Knowledge remains unknown rather than inferring beliefs or world truth from mention, dialogue, dreams, or later revelations. No suggestion changes canon or approves a scene; source-bound author review remains necessary.

The fixture is tiny, synthetic, and available during development, so the result is exploratory and does not establish generalization. The narrator-switch and book-chronology cases remain misses. Neither this diagnostic nor the tests constitute independent author review, release certification, or evidence about private manuscripts. No manuscript was sent to a hosted model.
