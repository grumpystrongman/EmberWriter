# Stage 2: nonadjacent contradiction detection

Status: implementation evidence only; no release certification or human review.

The Knowledge Lab previously compared only adjacent approved claims. An older
open-ended location claim could still overlap a later claim even when an
intervening location claim had ended. It now also checks nonadjacent pairs for
overlapping exclusive states, retaining both citations and requiring author
review. Adjacent history remains unchanged. This is a possible conflict, not a
determination of truth. It does not infer facts or promote proposals.

Synthetic regression coverage exercises the missed pair, an expired intervening
claim, citations and the earlier-book cutoff.

Validation from `backend` on Python 3.14:

- `py -3.14 -m pytest tests/test_series_knowledge_lab.py tests/test_series_knowledge_golden.py tests/test_series_scene_gold.py -q -p no:cacheprovider --basetemp=../.stage2-test-temp`: 77 passed.
- `py -3.14 -m ruff check app/series_knowledge_lab.py tests/test_series_knowledge_lab.py`: passed.
- The first pytest attempt without `--basetemp` failed at fixture setup because
  the default user temporary directory was inaccessible; no tests ran.

Scorecard assessment: no score increase is justified by this narrow synthetic
regression. SER-02 through SER-10 remain subject to their existing evidence
and human-review requirements. The 50 independently author-reviewed cross-book
questions, real literary inference quality, and independent author and expert
signoff remain outstanding. No private source text was used for this change.
