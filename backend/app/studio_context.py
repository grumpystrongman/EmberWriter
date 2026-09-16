from __future__ import annotations

from .character_voice import build_character_voice_context
from .chemistry import build_chemistry_context
from .craft import build_craft_context
from .models import CraftControls
from .storage import read_text, search_story
from .story_intelligence import build_character_context, relevant_character_names

STUDIO_CONTEXT_SENTINEL = "__EMBER_STUDIO_CONTEXT_V1__"
_CONTEXT_SEPARATOR = "\n\n---\n\n"
_SAFE_RETRIEVAL_PREFIXES = ("world/", "timeline/", "relationships/")


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


def build_studio_context(
    slug: str,
    prompt: str,
    controls: CraftControls,
    *,
    max_chars: int = 36000,
) -> tuple[str, list[str], str, list[str]]:
    """Build scene-focused context without retrieving unrelated manuscript prose.

    Studio is deliberately not a continuation surface. The current author prompt is the
    authoritative scene brief, so old chapter excerpts are more likely to derail generation
    than to help it. Studio therefore uses project settings, author style, explicitly named
    character dossiers/state, relationship chemistry, character voice, and narrowly scoped
    world/timeline/relationship references. It never retrieves manuscript/, source_archive/,
    import/, or arbitrary note prose.
    """
    sections: list[str] = []
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

    # World/timeline/relationship references can help with location and canon, but prose from
    # chapters and imports is intentionally excluded so a prior scene cannot become the model's
    # accidental continuation target.
    safe_hits = 0
    for hit in search_story(slug, prompt, limit=30):
        path = str(hit.get("path", ""))
        if not path.startswith(_SAFE_RETRIEVAL_PREFIXES):
            continue
        _add_file(
            slug,
            sections,
            files,
            seen,
            path,
            label="Relevant canon reference",
            char_limit=4500,
        )
        safe_hits += 1
        if safe_hits >= 4:
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
