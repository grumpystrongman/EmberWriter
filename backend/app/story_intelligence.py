from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .memory import list_memory
from .storage import project_root, read_text

_NAME_STOPWORDS = {"chapter", "scene", "someone", "something", "unknown", "reader", "narrator"}


def _display_name_from_dossier(slug: str, path: Path) -> str:
    relative = str(path.relative_to(project_root(slug))).replace("\\", "/")
    try:
        content = read_text(slug, relative)
    except (OSError, ValueError, FileNotFoundError):
        content = ""
    for line in content.splitlines()[:12]:
        if line.startswith("# ") and line[2:].strip():
            return line[2:].strip()
    return path.stem.replace("-", " ").replace("_", " ").strip().title()


def _dossiers(slug: str) -> dict[str, str]:
    root = project_root(slug) / "characters"
    if not root.exists():
        return {}
    dossiers: dict[str, str] = {}
    for path in root.iterdir():
        if not path.is_file() or path.name.lower() == "readme.md":
            continue
        if path.suffix.lower() not in {".md", ".txt", ".json", ".yaml", ".yml"}:
            continue
        name = _display_name_from_dossier(slug, path)
        if name:
            dossiers[name.casefold()] = str(path.relative_to(project_root(slug))).replace("\\", "/")
    return dossiers


def _looks_like_character_name(value: str) -> bool:
    cleaned = value.strip().strip(".,:;!?\"'")
    words = cleaned.split()
    if not 1 <= len(words) <= 4:
        return False
    if cleaned.casefold() in _NAME_STOPWORDS:
        return False
    return all(word[:1].isupper() for word in words if word)


def _character_fact(fact: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": fact["kind"],
        "predicate": fact["predicate"],
        "object": fact["object"],
        "source_path": fact["source_path"],
        "confidence": fact["confidence"],
        "importance": fact["importance"],
        "chapter_order": fact["chapter_order"],
        "metadata": fact.get("metadata", {}),
    }


def _target_from_relationship(
    fact: dict[str, Any],
    known_names: dict[str, str],
) -> str:
    metadata = fact.get("metadata") or {}
    explicit = str(metadata.get("target", "")).strip()
    if explicit:
        return explicit

    obj = str(fact["object"]).strip()
    exact = known_names.get(obj.casefold())
    if exact:
        return exact

    for folded, display in sorted(known_names.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(folded)}\b", obj.casefold()):
            return display
    return obj if _looks_like_character_name(obj) else ""


def build_story_intelligence(slug: str) -> dict[str, Any]:
    dossiers = _dossiers(slug)
    facts = list_memory(slug, limit=5000)

    known_names: dict[str, str] = {}
    for folded, path in dossiers.items():
        known_names[folded] = _display_name_from_dossier(slug, project_root(slug) / path)

    for fact in facts:
        if fact["kind"] in {"character_state", "character_knowledge"}:
            subject = str(fact["subject"]).strip()
            if subject:
                known_names.setdefault(subject.casefold(), subject)
        if fact["kind"] == "relationship":
            subject = str(fact["subject"]).strip()
            if subject:
                known_names.setdefault(subject.casefold(), subject)
            obj = str(fact["object"]).strip()
            if _looks_like_character_name(obj):
                known_names.setdefault(obj.casefold(), obj)

    profiles: dict[str, dict[str, Any]] = {}
    for folded, display in known_names.items():
        profiles[folded] = {
            "name": display,
            "dossier_path": dossiers.get(folded),
            "state": [],
            "knowledge": [],
            "relationships": [],
            "other_facts": [],
            "latest_chapter": 0,
        }

    relationships: list[dict[str, Any]] = []
    for fact in facts:
        subject_key = str(fact["subject"]).strip().casefold()
        profile = profiles.get(subject_key)
        if profile:
            converted = _character_fact(fact)
            if fact["kind"] == "character_state":
                profile["state"].append(converted)
            elif fact["kind"] == "character_knowledge":
                profile["knowledge"].append(converted)
            elif fact["kind"] == "relationship":
                profile["relationships"].append(converted)
            elif fact["kind"] in {"ability", "object", "location", "canon"}:
                profile["other_facts"].append(converted)
            profile["latest_chapter"] = max(profile["latest_chapter"], fact["chapter_order"])

        if fact["kind"] != "relationship":
            continue
        source = known_names.get(subject_key, str(fact["subject"]).strip())
        target = _target_from_relationship(fact, known_names)
        if not source or not target:
            continue
        metadata = fact.get("metadata") or {}
        relationships.append(
            {
                "source": source,
                "target": target,
                "state": fact["predicate"],
                "detail": str(metadata.get("detail", "")).strip(),
                "source_path": fact["source_path"],
                "chapter_order": fact["chapter_order"],
                "confidence": fact["confidence"],
                "importance": fact["importance"],
            }
        )

    for profile in profiles.values():
        for key in ("state", "knowledge", "relationships", "other_facts"):
            profile[key].sort(
                key=lambda item: (item["chapter_order"], item["importance"], item["confidence"]),
                reverse=True,
            )
            profile[key] = profile[key][:40]

    relationships.sort(
        key=lambda item: (item["chapter_order"], item["importance"], item["confidence"]),
        reverse=True,
    )
    characters = sorted(profiles.values(), key=lambda item: (item["latest_chapter"], item["name"]), reverse=True)
    return {"characters": characters, "relationships": relationships[:200]}


def build_character_context(slug: str, names: list[str]) -> str:
    wanted = {name.casefold() for name in names if name.strip()}
    if not wanted:
        return ""
    intelligence = build_story_intelligence(slug)
    selected = [item for item in intelligence["characters"] if item["name"].casefold() in wanted]
    if not selected:
        return ""

    lines = ["## Character intelligence"]
    for profile in selected:
        lines.append(f"### {profile['name']}")
        if profile["dossier_path"]:
            lines.append(f"Dossier: {profile['dossier_path']}")
        for label, key in (("Current state", "state"), ("Knowledge", "knowledge"), ("Relationships", "relationships")):
            entries = profile[key][:12]
            if not entries:
                continue
            lines.append(f"{label}:")
            for fact in entries:
                lines.append(
                    f"- {fact['predicate']} — {fact['object']} "
                    f"(ch {fact['chapter_order'] or '?'}, source {fact['source_path']})"
                )
    return "\n".join(lines)
