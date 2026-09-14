from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from .binder import get_binder
from .provenance_store import revision_rows, text_hash
from .storage import project_root, read_text
from .style_fidelity import STYLE_FIDELITY_PATH

WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'’-]*\b")
VOICE_PROFILE_PATH = "style/voice-profile.json"


def draft_documents(slug: str) -> list[dict[str, str]]:
    state = get_binder(slug)
    node_map = {node.id: node for node in state.nodes}
    draft = next((node_map[node_id] for node_id in state.roots if node_map[node_id].title == "Draft"), None)
    if draft is None:
        return []
    children: dict[str, list[Any]] = defaultdict(list)
    for node in state.nodes:
        if node.parent_id:
            children[node.parent_id].append(node)
    for nodes in children.values():
        nodes.sort(key=lambda node: node.position)
    result: list[dict[str, str]] = []

    def visit(parent_id: str) -> None:
        for node in children.get(parent_id, []):
            if node.kind == "folder":
                visit(node.id)
            elif node.path and not node.custom_metadata.get("source_missing"):
                result.append({"path": node.path, "binder_node_id": node.id})

    visit(draft.id)
    return result


def artifact_counts(slug: str) -> dict[str, int | bool]:
    root = project_root(slug)

    def count_files(relative: str) -> int:
        directory = root / relative
        return sum(1 for path in directory.rglob("*") if path.is_file()) if directory.exists() else 0

    return {
        "characters": count_files("characters"),
        "world": count_files("world"),
        "relationships": count_files("relationships"),
        "timeline": count_files("timeline"),
        "scenes": count_files("scenes"),
        "research": count_files("research"),
        "notes": count_files("notes"),
        "voice_profile": (root / VOICE_PROFILE_PATH).exists(),
        "style_fidelity": (root / STYLE_FIDELITY_PATH).exists(),
    }


def document_fingerprints(slug: str) -> tuple[list[dict[str, Any]], int, str, dict[str, list[dict]]]:
    revisions = revision_rows(slug)
    by_path: dict[str, list[dict]] = defaultdict(list)
    for row in revisions:
        by_path[row["path"]].append(row)
    documents: list[dict[str, Any]] = []
    project_parts: list[str] = []
    total_words = 0
    for item in draft_documents(slug):
        try:
            text = read_text(slug, item["path"])
        except (FileNotFoundError, OSError, ValueError):
            continue
        current_hash = text_hash(text)
        words = len(WORD_RE.findall(text))
        total_words += words
        project_parts.append(f"{item['path']}:{current_hash}")
        history = by_path.get(item["path"], [])
        documents.append({
            "path": item["path"],
            "binder_node_id": item["binder_node_id"],
            "current_hash": current_hash,
            "words": words,
            "revisions": len(history),
            "first_revision_at": history[0]["created_at"] if history else None,
            "latest_revision_at": history[-1]["created_at"] if history else None,
            "revision_sources": sorted({row["source"] for row in history}),
        })
    return documents, total_words, text_hash("\n".join(sorted(project_parts))), by_path
