from __future__ import annotations

import re

BODY_STATE_CONTRACT = """INTIMACY BODY-STATE / CHOREOGRAPHY CONTRACT:

ANATOMY IS IMMUTABLE CANON
- Treat anatomy as immutable character metadata.
- Never infer anatomy from gender identity, pronouns, presentation, trans/cis status, sexual role, dominance, submission, or genre convention.
- A body part belongs permanently to its established owner unless author canon explicitly changes that fact.
- Never silently substitute generic heterosexual or cisgender anatomy templates for established character anatomy.

SEXUAL ROLE IS DYNAMIC STATE
- Treat sexual role as dynamic scene state.
- Penetrative/receptive, oral/manual, dominant/submissive, active/passive, top/bottom, and position are current actions, not gender traits.
- A participant may change role during a scene, but the physical repositioning required for that change must occur on page.

MAINTAIN PHYSICAL STATE
Before writing every physical beat, silently track each participant's:
- body position: standing, seated, kneeling, crouched, lying, etc.
- orientation: facing toward, away, above, below, beside, behind
- torso orientation
- hip/pelvis orientation
- leg position
- approximate distance from the other participant(s)
- left-hand location
- right-hand location
- mouth activity and reachable area
- established intimate anatomy
- relevant genital position
- clothing state
- current contact points
- penetration state
- current physical action
- intended next physical action

CONTACT MUST HAVE OWNERSHIP
Internally represent physical contact as:
ACTOR.BODY_PART -> RECEIVER.BODY_LOCATION

Every possessive pronoun must resolve to the correct body owner.
Never accidentally transfer ownership of a tongue, hand, penis, breast, leg, anus, mouth, or other body part because the prose changed grammatical subject.

PENETRATION MUST HAVE A SOURCE AND TARGET
Represent penetration internally as:
SOURCE_OWNER.SOURCE -> RECEIVER.RECEIVING_LOCATION

Track:
- source owner
- exact penetrating body part or object
- receiving participant
- exact receiving anatomical location
- whether penetration is occurring now
- approximate depth only within realistic anatomical capability
- orientation required to maintain it

If source or receiving target cannot be determined from current body state, do not use penetration-dependent language.
A position label such as missionary, doggy style, from behind, straddling, or face-to-face NEVER supplies the receiving anatomy by itself.

Words such as inside, deeper, fill, filled, stretch, take, enter, push into, and thrust into are STATE-DEPENDENT vocabulary.
Use them only when the current physical state establishes exactly WHAT is entering WHAT.

PHYSICAL CAPABILITY IS NOT METAPHORICAL
Normal anatomy retains normal dimensions, flexibility, range of motion, and reach unless explicit story canon establishes supernatural alteration.

Do not make a body part larger, longer, more flexible, hollow, penetrative, or mechanically capable simply to intensify prose.

Examples:
- A penis is not an open cavity.
- Fingers, hands, or tongues cannot be placed inside a penis.
- A person's head or face cannot enter an anal opening.
- A tongue may contact an anal opening and may provide limited shallow penetration, but it cannot extend deeply through an anal canal, enter a rectum to implausible depth, or fill a receiving partner completely.
- A mouth cannot simultaneously occupy anatomically incompatible locations.
- A participant penetrating from a rear-facing configuration cannot simultaneously use their own mouth on the receiver's front genitalia unless the prose first establishes a different physically reachable configuration.
- Oral stimulation and penetration may occur simultaneously only when the described geometry makes both actions reachable; a keyword such as "simultaneously" does not make incompatible positions possible.
- Claims such as "filled twice over" require two actual, physically compatible penetrating/stimulating sources and identified targets.
- A hand cannot touch two distant body regions simultaneously unless it moves between them.
- A body part cannot reach through another solid body region.
- Genitals do not automatically touch one another merely because they belong to the same person.

REACHABILITY CHECK
Before every new action, silently verify:
1. Can the acting body part physically reach the target?
2. Are the participants facing the correct direction?
3. Is the actor in front, behind, beside, above, or below the receiver as required?
4. Does the current leg/hip/torso position permit the action?
5. Is another body part currently occupied elsewhere?
6. Does this action require a position change?

If a position change is required, write that transition BEFORE the new action.

NO TELEPORTATION
Do not teleport hands, mouths, heads, hips, legs, genitals, or entire bodies between incompatible positions.

Examples such as facing away -> face-to-face, behind -> between the legs, standing -> lying, clothed -> naked, external contact -> penetration, or penetrating -> suddenly across the room require an observable transition when the transition matters physically.

SCENE INTENT IS DISTINCT FROM CURRENT ACTION
Track:
- AGREED / REQUESTED ACT
- CURRENT ACT
- ESCALATION TARGET
- PENETRATION STATE
- REQUIRED TRANSITION

Do not silently replace the requested central act with another act merely because both involve the same anatomical region.

If the scene establishes one intended activity but performs preparatory or different activity first, preserve that distinction and continue progressing toward the intended activity unless the characters explicitly change course.

CONTINUITY FREEZE-FRAME
Before every paragraph containing significant physical action, silently reconstruct the scene as if drawing a still frame.

Verify:
- everyone can physically occupy the stated position
- all limbs and body parts have consistent owners
- all contact points are reachable
- no body part has teleported
- penetration source and target remain consistent
- clothing state remains consistent
- the next action can physically follow from the current one

If the still frame cannot be drawn without contradiction, repair the physical setup before continuing.

PROGRESSION
Do not repeat an earlier manual, oral, penetrative, or positioning beat merely to increase intensity.

Progress by changing action, changing position, changing participant response, changing rhythm/technique, pausing, reversing, escalating, de-escalating, or transitioning into the requested next act.

Repeated adjectives are not physical progression.

Physical clarity exists to support character, emotion, consent, relationship meaning, magical resonance, and story consequence. Do not turn the scene into an anatomical instruction manual, but never sacrifice physical coherence for heightened language."""

BODY_STATE_LEDGER_INSTRUCTION = """SILENT PHYSICAL STATE LEDGER:

For intimate physical scenes, maintain an internal state ledger while generating prose.

Do NOT print this ledger into manuscript output.

For each participant maintain:

CHARACTER:
  anatomy:
    confirmed_body_parts:
    explicitly_absent_body_parts:
    unknown_body_parts:
  pose:
  torso_orientation:
  pelvis_orientation:
  facing:
  location_relative_to_others:
  legs:
  left_hand:
  right_hand:
  mouth:
  relevant_genital_position:
  clothing_state:
  current_contacts:

SCENE:
  requested_act:
  current_act:
  escalation_target:
  penetration_active:
  penetration_source:
  penetration_target:
  preparation_state:
  required_transition:
  completed_actions:
  immediately_previous_position:

Before writing a new physical action:
1. Read the current ledger.
2. Check whether the action is physically reachable.
3. Check whether the acting body part is available.
4. Check body-part ownership.
5. Check anatomy capability.
6. Check whether a transition is required.
7. If required, narrate the transition first.
8. Update the ledger after the action.

Never infer unknown anatomy in order to make the next action possible.

If prose intensity conflicts with physical possibility, physical possibility wins.

If a phrase would require anatomy to behave unlike that anatomy normally behaves, replace the phrase rather than altering the body state.

After every significant position change or penetration-state change, reconstruct the complete freeze-frame before continuing."""

PLANNING_CONTINUITY_RULES = """For intimate scene planning:
- Preserve author-owned anatomy exactly.
- Never infer anatomy or sexual role from gender.
- Treat anatomy as immutable character metadata and sexual role as dynamic scene state.

For intimacy_notes, plan the physical progression in plain, non-prose language.

When relevant include entries using these prefixes:

START_STATE:
Describe each participant's starting pose, orientation, clothing state, and relative location.

REQUESTED_ACT:
The central intimate activity the author's scene is intended to deliver.

CURRENT_ACT:
What the participants are physically doing at the start of the relevant beat.

ESCALATION_TARGET:
What physical action the current activity is progressing toward.

CONTACT_STATE:
Important body-part contacts using ACTOR.BODY_PART -> RECEIVER.BODY_LOCATION.

PENETRATION_STATE:
NONE or SOURCE_OWNER.SOURCE -> RECEIVER.RECEIVING_LOCATION.

REQUIRED_TRANSITION:
Any repositioning necessary before the next major physical action.

CAPABILITY_CONSTRAINTS:
Any anatomy/reach limitations especially important to this choreography.

END_STATE:
Important final body/relationship/magical state produced by the encounter.

Every major position change must include a transition beat.

Every penetrative act must identify both source and receiving anatomical target.

Do not plan actions requiring impossible reach, impossible anatomy, body-part teleportation, simultaneous incompatible positions, or anatomical capability beyond established canon.

Preparatory stimulation and the requested central act are different scene states. Do not mark the requested act complete merely because preparation involving the same anatomical region occurred."""

VERIFIER_CONTINUITY_INSTRUCTION = (
    "For adult intimacy, independently verify physical choreography. "
    "physical_continuity is true only when the scene can be reconstructed as a physically coherent sequence of body states. "
    "Check anatomy ownership, pronoun ownership, body position, facing direction, relative location, hand placement, "
    "mouth placement, hip/pelvis orientation, clothing state, contact points, reachability, and major position transitions. "
    "Treat anatomy as immutable character metadata and sexual role as dynamic scene state. "
    "Never infer anatomy from gender identity or sexual role. "
    "For every penetrative action identify SOURCE_OWNER.SOURCE -> RECEIVER.RECEIVING_LOCATION. "
    "If the source, target, orientation, or transition needed to establish penetration is materially unclear, "
    "physical_continuity must be false. "
    "Enforce normal anatomical capability unless explicit supernatural canon changes it. "
    "A penis is external anatomy and not an open cavity. "
    "A head or face cannot enter an anal opening. "
    "A tongue cannot behave like a penis, extend implausibly deep into an anal canal or rectum, or fill another participant completely. "
    "A position label such as missionary, doggy style, from behind, or straddling does not identify receiving anatomy. "
    "Bare phrases such as 'entered her', 'slid in', 'filled him', or 'pushed deeper' cannot establish a new penetration state unless the exact receiving anatomy is already clear. "
    "A mouth has one current reachable location. If the same actor is penetrating from behind and is also described using their mouth on the receiver's front genitalia without a repositioning that makes both reachable, physical_continuity must be false. "
    "Claims of double or 'twice over' filling require two physically compatible sources and explicit targets. "
    "For standard positions, verify conventional geometry rather than the label alone: missionary/face-to-face requires the receiver on their back with the partner in front/between the legs; doggy/rear requires the receiver facing away with hips accessible and the partner behind. "
    "A two-person scene cannot have the same actor giving oral to the receiver's penis while that actor's penis simultaneously penetrates the receiver from behind. "
    "Hands, mouths, genitals, and bodies cannot teleport between incompatible locations. "
    "Distinguish preparation from the requested central activity. Performing oral or manual stimulation near an anatomical region "
    "does not automatically mean a requested penetration or other central act occurred. "
    "When physical_continuity is false, the reason MUST identify the first concrete contradiction in brief non-graphic terms, "
    "for example: 'A participant remains behind their partner but the next action requires access to the front of the pelvis without repositioning.' "
    "This reason will be used by the repair pass, so identify the actual physical problem rather than merely saying the scene is confusing."
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
_HEAD_IN_ANAL_OPENING = re.compile(
    r"\b(?:head|face|skull)\b"
    r"[^.!?\n]{0,100}"
    r"\b(?:inside|into|through|past)\b"
    r"[^.!?\n]{0,80}"
    r"\b(?:anus|anal\s+sphincter|sphincter|rectum|anal\s+canal)\b",
    re.IGNORECASE,
)
_ANAL_OPENING_AROUND_HEAD = re.compile(
    r"\b(?:anus|anal\s+sphincter|sphincter|rectum|anal\s+canal)\b"
    r"[^.!?\n]{0,100}"
    r"\b(?:around|enclosing|engulfing)\b"
    r"[^.!?\n]{0,60}"
    r"\b(?:head|face|skull)\b",
    re.IGNORECASE,
)
_TONGUE_DEEP_ANAL_CANAL = re.compile(
    r"\btongue\b"
    r"[^.!?\n]{0,180}"
    r"\b(?:rectum|"
    r"deep(?:ly)?\s+(?:inside|into)\s+(?:(?:his|her|their|the)\s+|(?:[A-Za-z][A-Za-z'’-]{1,30}['’]s)\s+)?(?:anus|anal\s+canal)|"
    r"depths?\s+of\s+(?:(?:his|her|their|the)\s+|(?:[A-Za-z][A-Za-z'’-]{1,30}['’]s)\s+)?(?:anus|anal\s+canal))\b",
    re.IGNORECASE,
)

_BARE_PENETRATION_PRONOUN = re.compile(
    r"\b(?:enter(?:ed|ing)?|penetrat(?:ed|ing)?|filled?|fill(?:ed|ing)?)\s+(?:her|him|them|me|you)\b",
    re.IGNORECASE,
)
_BARE_SLID_IN = re.compile(r"\bslid\s+in\b", re.IGNORECASE)
_PENETRATION_ACTION = re.compile(
    r"\b(?:penetrat\w*|thrust\w*|fuck\w*|enter(?:ed|ing)?|slid\s+(?:in|inside)|"
    r"push(?:ed|ing)?\s+(?:in|inside)|drov(?:e|en)\s+[^.!?\n]{0,50}\binside|fill(?:ed|ing)?)\b",
    re.IGNORECASE,
)
_EXACT_PENETRATION_TARGET = re.compile(
    r"\b(?:anus|anal\s+opening|asshole|rectum|mouth|throat|vagina|vaginal\s+opening)\b",
    re.IGNORECASE,
)
_PENETRATION_SETUP = re.compile(
    r"\b(?:align(?:ed|ing)?\s+(?:himself|herself|themself|themselves)|between\s+(?:her|his|their)\s+legs|"
    r"for\s+penetration|position(?:ed|ing)?\s+(?:himself|herself|themself|themselves))\b",
    re.IGNORECASE,
)
_WITHDRAWAL = re.compile(r"\b(?:withdrew|pulled\s+out|slid\s+out|disengaged)\b", re.IGNORECASE)

_PENIS_INSIDE_PRONOUN = re.compile(
    r"\b(?:penis|cock|dick)\b[^.!?\n]{0,100}\b(?:inside|within|deep\s+in)\s+(?:her|him|them|me|you)\b",
    re.IGNORECASE,
)
_ORAL_ON_POSSESSIVE_PENIS = re.compile(
    r"\b(?:took|takes|taking|suck(?:ed|ing)?|lick(?:ed|ing)?|mouth\s+(?:closed|worked|moved))\b"
    r"[^.!?\n]{0,120}\b(?:her|his|their)\s+(?:penis|cock|dick)\b|"
    r"\b(?:her|his|their)\s+(?:penis|cock|dick)\b[^.!?\n]{0,100}\b(?:mouth|suck\w*|lick\w*)\b",
    re.IGNORECASE,
)
_TONGUE_PROBING_INSIDE_NEAR_PENIS = re.compile(
    r"\b(?:penis|cock|dick)\b[^.!?\n]{0,150}\btongue\b[^.!?\n]{0,100}\b(?:prob(?:e|ed|ing)?\s+inside|inside)\b|"
    r"\btongue\b[^.!?\n]{0,100}\b(?:prob(?:e|ed|ing)?\s+inside|inside)\b[^.!?\n]{0,150}\b(?:penis|cock|dick)\b",
    re.IGNORECASE,
)
_TONGUE_UNTARGETED_INSIDE = re.compile(
    r"\btongue\b[^.!?\n]{0,120}\b(?:prob(?:e|ed|ing)?\s+inside|inside)\b",
    re.IGNORECASE,
)
_REAR_GEOMETRY = re.compile(
    r"\b(?:from\s+behind|behind\s+(?:her|him|them)|facing\s+away|on\s+(?:her|his|their)\s+stomach|"
    r"hands?\s+and\s+knees?|all\s+fours|kneeling\s+behind)\b",
    re.IGNORECASE,
)


def hard_choreography_failure(draft: str) -> str:
    """Reject only high-confidence anatomy/choreography failures before semantic verification."""
    if not draft.strip():
        return ""

    if _HEAD_IN_ANAL_OPENING.search(draft) or _ANAL_OPENING_AROUND_HEAD.search(draft):
        return (
            "physical continuity failure: draft gives a head or face impossible penetrative "
            "access to an anal opening"
        )

    if _TONGUE_DEEP_ANAL_CANAL.search(draft):
        return (
            "physical continuity failure: draft gives a tongue penetrative depth "
            "beyond normal anatomical capability"
        )

    if _INSIDE_PENIS.search(draft):
        return "physical continuity failure: draft treats a penis as an open cavity"

    if _TONGUE_PROBING_INSIDE_NEAR_PENIS.search(draft):
        return (
            "physical continuity failure: tongue/inside language near penis anatomy leaves the "
            "contact target physically impossible or undefined"
        )

    for paragraph in re.split(r"\n\s*\n", draft):
        if (
            _REAR_GEOMETRY.search(paragraph)
            and _ORAL_ON_POSSESSIVE_PENIS.search(paragraph)
            and _PENIS_INSIDE_PRONOUN.search(paragraph)
        ):
            return (
                "physical continuity failure: the same two-person rear configuration combines "
                "oral access to the receiver's penis with simultaneous penetration by the actor's penis"
            )

    penetration_target_established = False
    previous_sentence = ""
    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?…])\s+|\n+", draft)
        if part.strip()
    ]
    for sentence in sentences:
        if (
            _TONGUE_UNTARGETED_INSIDE.search(sentence)
            and _PENIS_TERMS.search(previous_sentence)
            and not _EXACT_PENETRATION_TARGET.search(sentence)
        ):
            return (
                "physical continuity failure: tongue/inside language near penis anatomy leaves the "
                "contact target physically impossible or undefined"
            )
        if _WITHDRAWAL.search(sentence):
            penetration_target_established = False
        has_action = bool(_PENETRATION_ACTION.search(sentence))
        has_exact_target = bool(_EXACT_PENETRATION_TARGET.search(sentence))
        if has_action and has_exact_target:
            penetration_target_established = True
        bare_start = bool(_BARE_PENETRATION_PRONOUN.search(sentence))
        slid_in = bool(_BARE_SLID_IN.search(sentence)) and bool(
            _PENETRATION_SETUP.search(previous_sentence)
            or _PENETRATION_SETUP.search(sentence)
        )
        if (bare_start or slid_in) and not has_exact_target and not penetration_target_established:
            return (
                "physical continuity failure: a new penetration state begins without identifying "
                "the exact receiving anatomy"
            )
        previous_sentence = sentence

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
