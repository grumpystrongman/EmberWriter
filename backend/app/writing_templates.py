"""Author-controlled writing format templates. Never overwrite an existing document."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from .storage import project_root, save_text

# Complete, editable conventions rather than a genre keyword slapped onto prose.
TEMPLATES = [
    {"id":"horror-novel","title":"Horror novel","group":"Fiction","icon":"◈","description":"Dread, vulnerability and escalating consequences.",
     "format":"novel","genre":"horror","guidance":"Build unease through ordinary detail disrupted by the impossible. Establish the protagonist's vulnerability, a concrete source of dread and progressively costly decisions. Honor rules of the supernatural; avoid constant jump scares. Keep emotional consequences after frightening events.",
     "sections":[("Opening: the ordinary world","Show a recognizable routine and the first unsettling contradiction."),("Escalation","The danger becomes personal; the protagonist makes an irreversible choice."),("Aftermath and consequence","What did this terror change? Leave room for human reaction.")]},
    {"id":"science-fiction-novel","title":"Science fiction novel","group":"Fiction","icon":"✧","description":"Big ideas grounded in human stakes and coherent rules.",
     "format":"novel","genre":"science_fiction","guidance":"Introduce technology or speculative science through decisions, not a lecture. Define the cost, constraint and social impact of the premise. Make the human dilemma matter even if the science is extraordinary. Maintain consistent world rules.",
     "sections":[("The speculative premise","Show the imagined world through a character's immediate problem."),("Systems and consequences","Reveal how a scientific rule changes institutions, relationships or power."),("A consequential choice","Force a decision that tests the story's central idea.")]},
    {"id":"fantasy-novel","title":"Fantasy novel","group":"Fiction","icon":"✦","description":"Wonder, character growth, magic and living cultures.",
     "format":"novel","genre":"fantasy","guidance":"Give magic or the fantastic clear constraints and a social cost. Favor grounded character wants and culturally specific details over encyclopedic exposition. Let wonder and danger change character relationships.",
     "sections":[("The threshold","Establish a desire and the first encounter with the extraordinary."),("Rules and relationships","Show who holds power, how magic works, and what it costs."),("The first irreversible choice","Put the protagonist's values under pressure.")]},
    {"id":"mystery-novel","title":"Mystery / thriller","group":"Fiction","icon":"⌕","description":"Clues, suspense and fair investigative reveals.",
     "format":"novel","genre":"mystery","guidance":"Introduce a question readers can care about. Make clues discoverable in retrospect, suspects distinct and misdirection causally plausible. Give each revelation a new consequence. Do not solve mysteries using unforeshadowed information.",
     "sections":[("The central mystery","Introduce the incident and a compelling unresolved question."),("Clues and false assumptions","Track evidence, sources, suspects and the protagonist's mistaken belief."),("The cost of the truth","Show the next lead and what investigation jeopardizes.")]},
    {"id":"romance-novel","title":"Romance novel","group":"Fiction","icon":"♡","description":"Mutual desire, agency and changing relationships.",
     "format":"novel","genre":"romance","guidance":"Give both leads independent goals, meaningful agency and credible obstacles. Let connection change them through choices and vulnerability. Honor boundaries and consent. Escalate emotional stakes instead of relying on arbitrary misunderstandings.",
     "sections":[("Meet the stakes","Establish each lead's existing life and emotional wants."),("Attraction and friction","Show a revealing interaction and consequential choice."),("New vulnerability","What will intimacy cost or make possible?")]},
    {"id":"literary-fiction","title":"Literary fiction","group":"Fiction","icon":"❦","description":"Voice, subtext, layered character and thematic resonance.",
     "format":"novel","genre":"literary_fiction","guidance":"Lead with specificity of thought and observation. Use concrete scene detail and subtext to explore theme. Avoid treating every paragraph as an aphorism. Keep plot and emotional movement present.",
     "sections":[("A charged ordinary moment","Ground the narrator in place and tension."),("Contradiction","Show a difficult memory, encounter, or choice."),("An altered understanding","A subtle but consequential shift in perspective.")]},
    {"id":"short-story","title":"Short story","group":"Short forms","icon":"◇","description":"One defining change in a concentrated arc.",
     "format":"short_story","genre":"general","guidance":"Keep a narrow cast, one central pressure and a sharply observed turning point. Enter late; leave promptly after the emotional consequence. Avoid novel-scale subplots and excessive exposition.",
     "sections":[("Opening image and disturbance","A specific person faces a change in the status quo."),("Rising complication","Pressure and choice sharpen around one concern."),("Turn and final image","A decisive action or recognition and a resonant ending.")]},
    {"id":"flash-fiction","title":"Flash fiction","group":"Short forms","icon":"⋄","description":"An evocative miniature with a decisive turn.",
     "format":"flash_fiction","genre":"general","guidance":"Target 300–1,000 words. Start in motion, focus on a single tension, and end on a changed meaning rather than a twist for its own sake.",
     "sections":[("The moment","Enter the situation with one concrete image."),("The shift","Introduce the smallest meaningful conflict."),("The closing resonance","End just after perspective or action changes.")]},
    {"id":"personal-essay","title":"Personal essay","group":"Nonfiction","icon":"☷","description":"Reflective nonfiction built from lived experience.",
     "format":"essay","genre":"personal_essay","guidance":"Begin with a genuine question or scene. Separate remembered fact from interpretation. Let reflection grow from concrete detail; avoid a forced inspirational moral. Preserve first-person authenticity.",
     "sections":[("Scene or question","A specific observation that troubles or interests you."),("Experience and inquiry","What happened, what you thought then, and what remains uncertain."),("Reflection","What changes in your understanding, without pretending everything is resolved.")]},
    {"id":"academic-essay","title":"Academic / argumentative essay","group":"Nonfiction","icon":"§","description":"Claim, evidence, counterargument and reasoned conclusion.",
     "format":"essay","genre":"academic","guidance":"State an arguable thesis. Distinguish evidence from inference and clearly label any missing citations as TODOs. Address a serious counterargument fairly. Never invent academic sources, quotations or statistics.",
     "sections":[("Introduction and thesis","Context, research question and a contestable claim."),("Claim and evidence","Use verified evidence; add [CITATION NEEDED] where missing."),("Counterargument","State a strong opposing position and respond with evidence."),("Conclusion","Synthesize the reasoning and its limitations.")]},
    {"id":"screenplay","title":"Film / TV screenplay","group":"Scripts","icon":"▣","description":"Screen directions, visual action and speakable dialogue.",
     "format":"screenplay","genre":"screenplay","guidance":"Write filmable action in present tense. Use INT./EXT. sluglines, concise action blocks, uppercase character cues, natural dialogue and sparing parentheticals. Avoid unfilmable internal monologue and novel-style exposition. Plain text is a drafting aid, not industry-standard FDX/PDF pagination.",
     "sections":[("FADE IN:",""),("INT. LOCATION - DAY","A playable action beat. Describe what the audience can see and hear."),("CHARACTER","A line of dialogue that changes the scene."),("EXT. NEW LOCATION - NIGHT","Another meaningful visual beat.")],"skeleton":"FADE IN:\n\nINT. LOCATION - DAY\n\nA room holds its breath. Someone is waiting.\n\nCHARACTER\nWhat are we going to do now?\n\nCUT TO:\n\nEXT. NEW LOCATION - NIGHT\n\nThe consequence arrives.\n"},
    {"id":"stage-play","title":"Stage play","group":"Scripts","icon":"▤","description":"Acts, scenes, stageable movement and actor dialogue.",
     "format":"stage_play","genre":"stage_play","guidance":"Build for a physical stage: acts/scenes, manageable entrances, exits, props and lighting. Put action in concise parenthetical stage directions. Give actors playable objectives and subtext. Keep production practicality in view.",
     "sections":[("ACT I · SCENE 1",""),("SETTING","Describe the stage, light and essential props."),("CHARACTERS ON STAGE","List the characters present."),("DIALOGUE","Character names, speaking lines, and spare stage directions.")],"skeleton":"ACT I\n\nSCENE 1\n\nSETTING: A room with one table and a locked door. Evening.\n\n(AT RISE: One person waits by the door.)\n\nCHARACTER\nI thought you were never coming.\n\nOTHER CHARACTER\n(entering)\nI almost didn't.\n"},
    {"id":"podcast-script","title":"Podcast / audio drama","group":"Scripts","icon":"◉","description":"Dialogue, sound design and cues for listeners.",
     "format":"audio_script","genre":"audio_drama","guidance":"Write for listeners. Mark SFX/MUSIC sparingly, establish speaker identity through distinctive voices, make important action audible through sound and reaction. Avoid visually-dependent stage directions.",
     "sections":[("OPEN / SFX","Ambient sound and the first compelling spoken question."),("SCENE 1","Speaker names, dialogue and sound cues."),("SCENE 2","A change of place, stakes or soundscape."),("OUTRO","The last beat and audio transition.")],"skeleton":"SFX: Rain against the windows. A key turns.\n\nNARRATOR: By the time we arrived, the lights had gone out.\n\nSFX: A floorboard creaks.\n\nMARA: Did you hear that?\n"},
    {"id":"poetry","title":"Poetry","group":"Short forms","icon":"≈","description":"Rhythm, imagery and intentional line breaks.",
     "format":"poetry","genre":"poetry","guidance":"Let musicality and image lead. Choose form deliberately: free verse, fixed form, or prose poem. Use line breaks as meaning-making decisions, not decoration. Avoid generic abstract sentiment.",
     "sections":[("Image","Start with something tactile and unexpected."),("Movement","Let sound and thought complicate the image."),("Turn","Change the relationship between speaker and image.")]},
]
BY_ID = {item["id"]: item for item in TEMPLATES}


def catalog() -> list[dict]:
    return [{key: value for key, value in item.items() if key not in {"guidance", "sections", "skeleton"}}
            for item in TEMPLATES]


def preview(template_id: str, title: str) -> dict:
    if template_id not in BY_ID:
        raise ValueError("Unknown writing template")
    template = BY_ID[template_id]
    safe_title = title.strip()
    if not 1 <= len(safe_title) <= 160 or "\n" in safe_title or "\r" in safe_title:
        raise ValueError("Enter a document title (1–160 characters)")
    if "skeleton" in template:
        body = template["skeleton"]
    else:
        body = "\n\n".join(f"## {heading}\n\n<!-- {hint} -->" if hint
                           else f"## {heading}" for heading, hint in template["sections"])
    content = f"# {safe_title}\n\n{body.rstrip()}\n"
    guide = (f"# Writing guide: {template['title']}\n\n"
             f"**Form:** {template['format']} · **Genre:** {template['genre']}\n\n"
             f"{template['guidance']}\n\n"
             "## Author decisions\n\n"
             "- Audience and voice:\n- Point of view or narrator:\n- References and inspirations:\n"
             "- Things to avoid:\n\n"
             "This is a guide, not immutable canon. Your manuscript is yours to change.\n")
    return {"id": template_id, "title": safe_title, "format": template["format"],
            "genre": template["genre"], "description": template["description"],
            "content": content, "guide": guide}


def create(slug: str, template_id: str, title: str) -> dict:
    draft = preview(template_id, title)
    root = project_root(slug)
    if not (root / "project.json").is_file():
        raise FileNotFoundError(slug)
    stem = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:72] or "new-writing"
    destination: Path | None = None
    for number in range(1, 1001):
        candidate = root / "manuscript" / (f"{stem}.md" if number == 1 else f"{stem}-{number}.md")
        if not candidate.exists():
            destination = candidate
            break
    if destination is None:
        raise ValueError("Too many documents share this title")
    # Atomic exclusive create: never overwrite the author's existing work.
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as output:
        output.write(draft["content"])
    relative = destination.relative_to(root).as_posix()
    # Per-document guides do not clobber the existing author profile.
    guide_path = root / "style" / "templates" / f"{destination.stem}.md"
    guide_path.parent.mkdir(parents=True, exist_ok=True)
    with guide_path.open("x", encoding="utf-8") as output:
        output.write(draft["guide"])
    # A small project-local index makes the template accessible to the helper.
    index_path = root / ".ember" / "writing-templates.json"
    try:
        records = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
        if not isinstance(records, dict):
            records = {}
    except (OSError, ValueError):
        records = {}
    records[relative] = {"template_id": template_id, "style_guide": guide_path.relative_to(root).as_posix(),
                         "format": draft["format"], "genre": draft["genre"],
                         "created_at": datetime.now(UTC).isoformat()}
    index_path.parent.mkdir(parents=True, exist_ok=True)
    staging = index_path.with_suffix(".json.tmp")
    staging.write_text(json.dumps(records, indent=2), encoding="utf-8")
    staging.replace(index_path)
    from .binder import sync_binder
    sync_binder(slug)
    return {"path": relative, "guide_path": guide_path.relative_to(root).as_posix(),
            "format": draft["format"], "genre": draft["genre"], "template_id": template_id}
