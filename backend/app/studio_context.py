from __future__ import annotations

from .binder import get_binder
from .character_voice import build_character_voice_context
from .chemistry import build_chemistry_context
from .craft import build_craft_context
from .models import CraftControls, FRESH_WRITE_CONTEXT_SENTINEL
from .storage import read_text, search_story
from .story_intelligence import build_character_context, relevant_character_names

STUDIO_CONTEXT_SENTINEL = FRESH_WRITE_CONTEXT_SENTINEL
_CONTEXT_SEPARATOR = "\n\n---\n\n"
_BLOCKED_PROSE_PREFIXES = ("manuscript/", "source_archive/", "import/", ".ember/")


def _add_file(
    slug: str,
    sections: list[str],
    files: list[str],
    seen: set[str],
    path: str,
    *,
    label: str,
    char_limit: int,
) -> None:
    if path in seen:
        return
    try:
        text = read_text(slug, path).strip()
    except (FileNotFoundError, OSError, ValueError):
        return
    if not text:
        return
    seen.add(path)
    files.append(path)
    sections.append(f"## {label}\nSource: {path}\n\n{text[:char_limit]}")


def _binder_reference_nodes(slug: str):
    """Return non-Draft, non-Trash Binder documents that are safe as reference knowledge."""
    state = get_binder(slug)
    nodes = {node.id: node for node in state.nodes}
    root_title_by_id = {node_id: nodes[node_id].title for node_id in state.roots if node_id in nodes}

    def root_title(node) -> str:
        current = node
        visited: set[str] = set()
        while current.parent_id and current.parent_id not in visited:
            visited.add(current.parent_id)
            parent = nodes.get(current.parent_id)
            if parent is None:
                break
            current = parent
        return root_title_by_id.get(current.id, current.title)

    references = []
    for node in state.nodes:
        if not node.path or node.kind in {"folder", "trash"}:
            continue
        if node.custom_metadata.get("source_missing"):
            continue
        if root_title(node) in {"Draft", "Trash"}:
            continue
        normalized = node.path.replace("\\", "/")
        if normalized.startswith(_BLOCKED_PROSE_PREFIXES):
            continue
        references.append(node)
    return references


def _binder_catalog(reference_nodes) -> str:
    """Give the model a compact map of what the author has placed in the Binder."""
    lines = [
        "## Binder knowledge map",
        "These are author-provided reference documents. Use them as canon/creative guidance, not as prose to continue.",
    ]
    for node in reference_nodes:
        metadata: list[str] = []
        if node.synopsis.strip():
            metadata.append(f"synopsis: {node.synopsis.strip()}")
        if node.keywords:
            metadata.append("keywords: " + ", ".join(node.keywords[:12]))
        if node.label.strip():
            metadata.append(f"label: {node.label.strip()}")
        suffix = f" — {'; '.join(metadata)}" if metadata else ""
        lines.append(f"- {node.title} [{node.kind}] ({node.path}){suffix}")
    return "\n".join(lines)[:8000]


def build_studio_context(
    slug: str,
    prompt: str,
    controls: CraftControls,
    *,
    max_chars: int = 42000,
) -> tuple[str, list[str], str, list[str]]:
    """Build Binder-aware context for a fresh generation.

    Fresh Write/Studio generation starts from a blank prose boundary. Binder material is reference
    knowledge only: world, environment, characters, behavior, relationships, timeline, research,
    notes, style, summaries, and other author-provided reference material can inform the new scene,
    but Draft/manuscript prose is never supplied as something to continue. Explicit Continue mode is
    handled elsewhere and is the only mode that receives the current manuscript ending.
    """
    sections: list[str] = [
        (
            "## Fresh generation boundary\n"
            "Start the requested prose from a NEW first line. Do not continue, complete, quote, or imitate the ending of a prior scene. "
            "Everything below is reference knowledge only. Use it to preserve canon, environment, character behavior, voice, relationships, "
            "world rules, and continuity while beginning the exact new scene requested by the author."
        )
    ]
    files: list[str] = []
    seen: set[str] = set()

    _add_file(
        slug,
        sections,
        files,
        seen,
        "project.json",
        label="Project settings",
        char_limit=5000,
    )
    _add_file(
        slug,
        sections,
        files,
        seen,
        "style/author-profile.md",
        label="Author style",
        char_limit=7000,
    )
    _add_file(
        slug,
        sections,
        files,
        seen,
        "summaries/rolling-summary.md",
        label="Current story state",
        char_limit=7000,
    )

    reference_nodes = _binder_reference_nodes(slug)
    if reference_nodes:
        sections.append(_binder_catalog(reference_nodes))
    allowed_paths = {node.path for node in reference_nodes if node.path}

    names = relevant_character_names(slug, prompt, limit=6)
    if names:
        character_context = build_character_context(slug, names).strip()
        if character_context:
            sections.append(character_context)

        voice_context, voice_files = build_character_voice_context(slug, names)
        if voice_context.strip():
            sections.append(voice_context.strip())
            for path in voice_files:
                if path not in seen:
                    seen.add(path)
                    files.append(path)

        if len(names) >= 2:
            chemistry_context, chemistry_files = build_chemistry_context(slug, names)
            if chemistry_context.strip():
                sections.append(chemistry_context.strip())
                for path in chemistry_files:
                    if path not in seen:
                        seen.add(path)
                        files.append(path)

    # Retrieve the most relevant author-provided Binder references, regardless of whether they
    # live under World, Relationships, Research, Notes, Scenes, or another non-Draft area.
    relevant_hits = 0
    for hit in search_story(slug, prompt, limit=60):
        path = str(hit.get("path", ""))
        if path not in allowed_paths:
            continue
        _add_file(
            slug,
            sections,
            files,
            seen,
            path,
            label="Relevant Binder reference",
            char_limit=4500,
        )
        relevant_hits += 1
        if relevant_hits >= 8:
            break

    # If lexical retrieval found little, still provide a small amount of world/context reference
    # so a new scene is not generated in a vacuum merely because the prompt used different wording.
    if relevant_hits < 3:
        for node in reference_nodes:
            path = node.path or ""
            if not path.startswith(("world/", "relationships/", "timeline/", "characters/")):
                continue
            _add_file(
                slug,
                sections,
                files,
                seen,
                path,
                label="Binder canon reference",
                char_limit=2400,
            )
            relevant_hits += 1
            if relevant_hits >= 5:
                break

    craft_context, craft_files = build_craft_context(slug, controls)
    if craft_context.strip():
        sections.append(craft_context.strip())
    for path in craft_files:
        if path not in seen:
            seen.add(path)
            files.append(path)

    context = _CONTEXT_SEPARATOR.join(section for section in sections if section).strip()
    if len(context) > max_chars:
        context = context[:max_chars].rstrip()
    return context, files, craft_context, names
