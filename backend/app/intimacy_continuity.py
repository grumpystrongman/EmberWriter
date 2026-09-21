from __future__ import annotations

import re

BODY_STATE_CONTRACT = """INTIMACY BODY-STATE / CHOREOGRAPHY CONTRACT:
- Treat anatomy as immutable character metadata. Never infer anatomy from gender identity, pronouns, presentation, trans/cis status, or sexual role.
- Treat sexual role as dynamic scene state. Penetrative/receptive, oral/manual, dominant/submissive, and position are actions, not genders.
- Before writing each physical beat, silently track for every participant: body position, facing/orientation, left hand, right hand, mouth activity, relevant genital position, clothing state, current contact points, and whether penetration is occurring.
- Represent penetration internally as SOURCE -> TARGET. SOURCE is the penetrating body part/object; TARGET is the receiving anatomical location. If both cannot be named from the current state, do not write penetration-dependent language.
- Words such as inside, deeper, fill, filled, stretch, take, enter, and thrust into are state-dependent. Use them only when the current body state makes the source and target unambiguous.
- A penis is not an open cavity. External touching, gripping, stroking, oral contact, or contact with the tip never becomes fingers/hand/tongue being inside the penis.
- Do not teleport hands, mouths, hips, or bodies. If an action requires a new position or reach, write the physical transition first.
- Before each paragraph, verify reachability, orientation, pronoun ownership, anatomy ownership, contact points, penetration source/target, and required position changes.
- Do not repeat an earlier manual/oral/penetrative beat merely to increase intensity. Progress, deliberately change, pause, reverse, or return with a clear transition.
- Physical clarity supports character. Keep voice, emotion, consent, relationship meaning, and story consequences primary while making the mechanics easy to follow."""

PLANNING_CONTINUITY_RULES = """For intimate scene planning:
- Preserve author-owned anatomy exactly; never infer anatomy or sexual role from gender.
- In intimacy_notes, record the intended physical progression in plain, non-prose terms when body mechanics matter: starting position/orientation, major contact change, any penetration as SOURCE -> TARGET, and the transition required before a position/role change.
- A role change must include a physical repositioning beat.
- Do not plan anatomically impossible actions or use penetration words without a receiving anatomical target."""

VERIFIER_CONTINUITY_INSTRUCTION = (
    "For adult intimacy, also judge physical choreography. physical_continuity is true only when body positions, "
    "reachability, anatomy ownership, hand/mouth placement, and major transitions are coherent, and every penetrative "
    "action has an identifiable source and receiving anatomical target. Do not infer anatomy from gender. Treat a penis "
    "as external anatomy, not an open cavity; language placing fingers, a hand, or a tongue inside a penis is a hard failure. "
    "If the draft uses penetration-dependent language while the source/target or position is materially unclear, "
    "physical_continuity must be false."
)

_INSIDE_PENIS = re.compile(
    r"\b(?:inside|into)\s+(?:(?:his|her|their|the|a|an)\s+|(?:[A-Za-z][A-Za-z'’-]{1,30}['’]s)\s+)?(?:penis|cock|dick)\b",
    re.IGNORECASE,
)
_PENIS_TERMS = re.compile(r"\b(?:penis|cock|dick)\b", re.IGNORECASE)
_DIGIT_IN_PRONOUN = re.compile(
    r"\b(?:finger|fingers|thumb)\b[^.!?\n]{0,90}\b(?:inside|into)\s+(?:him|her|them)\b",
    re.IGNORECASE,
)
_RECEIVING_TARGET = re.compile(
    r"\b(?:anus|anal|asshole|rectum|mouth|throat|vagina|vaginal|vulva)\b",
    re.IGNORECASE,
)


def hard_choreography_failure(draft: str) -> str:
    """Reject only high-confidence anatomy/choreography failures before semantic verification."""
    if not draft.strip():
        return ""

    if _INSIDE_PENIS.search(draft):
        return "physical continuity failure: draft treats a penis as an open cavity"

    for paragraph in re.split(r"\n\s*\n", draft):
        if not _PENIS_TERMS.search(paragraph):
            continue
        if not _DIGIT_IN_PRONOUN.search(paragraph):
            continue
        if _RECEIVING_TARGET.search(paragraph):
            continue
        return (
            "physical continuity failure: finger penetration is described while penis handling is established, "
            "but no receiving anatomical target or repositioning is identified"
        )

    return ""
