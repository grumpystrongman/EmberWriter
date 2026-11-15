"""Predeclared synthetic literary interpretation evaluation, no LLM or manuscripts.

Gold scene breaks and narrative truths are authored fixture labels. Current
production behavior only creates bounded reading windows; it never predicts
scene identity, viewpoint, or character knowledge. A false split is not a
confirmed scene and must never be graded as an approved narrative interpretation.
"""
from __future__ import annotations

import hashlib
import json

from . import series_scene_reviews as reviews
from . import series_scene_windows as windows
from . import series_vault as vault

# Each test declares an exact expected narrative boundary between two fictional
# passages. A typography divider may or may not be a real scene transition.
# The false-positive and unmarked-boundary cases are intentionally adversarial.
GOLD = (
    ("scene_divider", "Explicit scene divider",
     "Mira stepped into the midnight harbor.", "\n***\n",
     "At dawn, Rowan opened the locked gate.", True,
     "third_limited", "Rowan", "unknown", "Scene break after typographic divider"),
    ("plain_paragraph", "Unmarked change of time and place",
     "Mira locked the tower before winter.", "\n\n",
     "Three months later, Rowan arrived in a desert palace.", True,
     "third_limited", "Rowan", "unknown", "Narrative change without visual divider"),
    ("first_person", "First-person scene change",
     "I spent the night watching the empty road.", "\n***\n",
     "When I woke in another city, the war was over.", True,
     "first_person", "narrator", "known", "First-person is not omniscient narration"),
    ("flashback", "Flashback is not the present scene",
     "Rowan stood beside the ruined bridge.", "\n\n",
     "Years earlier, his mother had buried a key beneath that same bridge.", True,
     "third_limited", "Rowan", "unknown", "Backwards story time, no separator"),
    ("dream", "Dream transition",
     "Mira fell asleep beneath the stars.", "\n***\n",
     "Inside her dream, the demolished gate stood whole again.", True,
     "third_limited", "Mira", "unknown", "Dream content is not objective history"),
    ("narrator_switch", "Viewpoint switches without a section heading",
     "Only Ada knew where she had hidden the letter.", "\n\n",
     "Across the city, Bex wondered whether the letter still existed.", True,
     "third_omniscient", "narrator", "unknown", "Narrative perspective needs examination"),
    ("unreliable_claim", "Speaker belief versus world truth",
     "Mira told Rowan that the harbor was safe.", "\n***\n",
     "The narrator explained that the harbor had been mined for weeks.", True,
     "third_omniscient", "narrator", "unknown", "Claim of safety is not world truth"),
    ("decorative_divider", "Decorative divider inside one scene",
     "A printed poster had a symbol below its headline:", "\n***\n",
     "Mira kept reading the same poster without changing place or time.", False,
     "third_limited", "Mira", "known", "Typographic marks are not always scene breaks"),
    ("dialogue_paragraph", "Dialogue paragraph inside continuing scene",
     "Mira said she was leaving. Rowan asked her to stay.", "\n\n",
     "Mira answered that she would return before midnight.", False,
     "third_limited", "Mira", "known", "Paragraph boundary is not a scene break"),
    ("chronology_belief", "Later revelation cannot overwrite earlier knowledge",
     "At the end of Book 1, Sabine believed the bridge safe.", "\n\n",
     "By Book 3, she learned that it had been sabotaged.", True,
     "third_limited", "Sabine", "unknown", "Character knowledge must stay scoped by book"),
    ("no_change", "Two paragraphs of one unbroken event",
     "Ada turned the handle and opened the door.", "\n\n",
     "Without leaving the room, Ada reached for the lamp.", False,
     "third_limited", "Ada", "known", "Ordinary paragraphs are not separate scenes"),
    ("long_unsplit", "Length-limited split must not claim a scene",
     ("The guard paced along the same wall and never changed his task. " * 155),
     "\n\n", ("The guard continued pacing the same wall until noon. " * 32),
     False, "third_limited", "guard", "known",
     "Window-size limits are not literary scene evidence"),
)

EXPECTED_FIXTURE_COUNT = 12


def _case(row: tuple) -> dict:
    case_id, label, left, separator, right, gold, pov, knower, knowledge, note = row
    text = left + separator + right
    return {
        "id": case_id, "label": label, "text": text,
        "gold_break": bool(gold), "gold_at": len(left + separator),
        "gold_pov": pov, "gold_knower": knower,
        "gold_knowledge": knowledge, "annotation": note,
    }


def score_boundary_candidates(cases: tuple[dict, ...] | None = None) -> dict:
    dataset = cases if cases is not None else tuple(_case(row) for row in GOLD)
    if not dataset:
        raise ValueError("Gold evaluation cannot use an empty fixture set")
    # Refuse malformed/ambiguous gold labels instead of silently altering scores.
    seen_ids: set[str] = set()
    for case in dataset:
        ident = case.get("id")
        content = case.get("text")
        at = case.get("gold_at")
        if not isinstance(ident, str) or not ident or ident in seen_ids:
            raise ValueError("Gold evaluation requires unique nonempty case IDs")
        seen_ids.add(ident)
        if not isinstance(content, str) or not content:
            raise ValueError("Empty fixture passage")
        if type(at) is not int or not 0 < at < len(content):
            raise ValueError("Gold boundary offset must fall inside its passage")
        if type(case.get("gold_break")) is not bool:
            raise ValueError("Gold scene boundary must be explicitly boolean")
        if case.get("gold_pov") not in reviews.POV - {"undetermined"}:
            raise ValueError("Gold POV category is invalid")
        if case.get("gold_knowledge") not in {"known", "unknown"}:
            raise ValueError("Gold character knowledge label is invalid")
    rows = []
    tp = fp = fn = tn = 0
    for case in dataset:
        content = case["text"]
        if not content:
            raise ValueError("Empty fixture passage")
        divisions = list(windows._windows(content, 0, len(content)))
        # All reading-window breaks are only *candidates*. We measure how
        # frequently those boundaries align with predeclared fixture gold.
        # Whitespace to the right of a printed marker is not a literary break.
        starts = sorted({start + len(content[start:end])-len(content[start:end].lstrip())
                         for start,end,_ in divisions[1:]})
        at = case["gold_at"]
        # Match at most ONE candidate to a gold boundary. Multiple nearby
        # navigation splits cannot all receive credit for the same scene.
        matches = [start for start in starts if abs(start-at) <= 3]
        matched = min(matches, key=lambda start: (abs(start-at), start)) if matches else None
        predicted = matched is not None
        actual = case["gold_break"]
        if actual:
            if predicted:
                tp += 1
            else:
                fn += 1
            fp += len(starts)-int(predicted)
        elif starts:
            fp += len(starts)
        else:
            tn += 1
        rows.append({
            "id":case["id"], "label":case["label"],
            "gold_scene_boundary":actual,
            "candidate_boundary_at_gold":predicted,
            "candidate_break_count":len(starts),
            "extraneous_breaks":len(starts)-int(predicted) if actual else len(starts),
            "gold_boundary_offset":at if actual else None,
            "candidate_starts":starts[:16],
            "matched_candidate_start":matched if actual else None,
            "boundary_result":"hit" if actual and predicted else
                              "miss" if actual else
                              "false_positive" if starts else "correct_rejection",
            "gold_pov":case["gold_pov"],
            "predicted_pov":"undetermined",
            "pov_grading":"abstained",
            "gold_character_knowledge":case["gold_knowledge"],
            "predicted_character_knowledge":"unknown",
            "knowledge_grading":"abstained" if case["gold_knowledge"]!="unknown"
                                else "safe_abstention",
            "annotation":case["annotation"],
            "synthetic_preview":case["text"][:280],
        })
    precision = tp/(tp+fp) if tp+fp else 0.0
    recall = tp/(tp+fn) if tp+fn else 0.0
    f1 = 2*precision*recall/(precision+recall) if precision+recall else 0.0
    known_pov = len(rows)
    known_knowledge = sum(c["gold_character_knowledge"]!="unknown" for c in rows)
    return {
        "dataset":"synthetic_literary_gold_v1",
        "fixture_sha256":hashlib.sha256(json.dumps(dataset, sort_keys=True,
                        ensure_ascii=False, default=str).encode("utf8")).hexdigest(),
        "case_count":len(rows),
        "boundary":{"true_positive":tp,"false_positive":fp,
                    "false_negative":fn,"true_negative":tn,
                    "precision":round(precision,4),"recall":round(recall,4),
                    "f1":round(f1,4)},
        "pov":{"gold_cases":known_pov,"prediction_coverage":0,
               "correct_predictions":0,"unsupported_predictions":0},
        "character_knowledge":{"gold_known_cases":known_knowledge,
                               "prediction_coverage":0,
                               "correct_predictions":0,
                               "unsupported_predictions":0},
        "cases":rows,
        "scene_interpretation_gate":"blocked",
        "automatic_scene_approval_allowed":False,
        "source_text_sent":False,
        "external_model_calls":False,
        "limitations":(
            "Synthetic, authored gold cases only. Current navigation windows "
            "are never scene labels. A hit measures proximity of a reading "
            "window boundary, not semantic recognition. POV/knowledge inference "
            "abstains; production scene approval requires human verification."
        ),
    }


def evaluate(series_id: str, *, book: int | None = None) -> dict:
    vault.series_detail(series_id)
    if book is not None and not 1 <= book <= 9999:
        raise ValueError("Invalid book for scene evaluation")
    report = score_boundary_candidates()
    staged = reviews.list_reviews(series_id, book=book)
    report["series_id"] = series_id
    report["book"] = book
    report["author_reviews"] = {
        "shown":len(staged),
        "source_verified":sum(bool(r["source_verified"]) for r in staged),
        "pending":sum(r["status"]=="proposed" for r in staged),
        "author_confirmed_scenes":sum(bool(r["author_confirmed_scene"]) for r in staged),
        "rejected":sum(r["status"]=="rejected" for r in staged),
        "limited_to_first":250,
        "cannot_be_used_as_gold_automatically":True,
    }
    return report
