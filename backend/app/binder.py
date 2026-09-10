from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from uuid import uuid4

from .binder_models import (
    BinderCollection,
    BinderCollectionCreate,
    BinderCollectionUpdate,
    BinderNode,
    BinderNodeCreate,
    BinderNodeUpdate,
    BinderReorderRequest,
    BinderState,
)
from .storage import get_project, project_root, read_text, save_text, utc_now

BINDER_PATH = "binder.json"
ROOT_TITLES = ("Draft", "Research", "Story Bible", "Trash")
STORY_BIBLE_FOLDERS = {
    "characters",
    "world",
    "relationships",
    "timeline",
    "scenes",
    "style",
    "summaries",
    "notes",
}
SKIPPED_FILES = {"project.json", BINDER_PATH}
WORD_RE = re.compile(r"\b[\w’'-]+\b", flags=re.UNICODE)


def _new_id() -> str:
    return uuid4().hex


def _file_title(slug: str, path: str) -> str:
    try:
        content = read_text(slug, path)
    except (FileNotFoundError, OSError, ValueError, UnicodeError):
        content = ""
    for line in content.splitlines()[:12]:
        stripped = line.strip()
        if stripped.startswith("# ") and stripped[2:].strip():
            return stripped[2:].strip()
    return PurePosixPath(path).stem.replace("-", " ").replace("_", " ").strip().title()


def _word_count(slug: str, path: str | None) -> int:
    if not path:
        return 0
    try:
        return len(WORD_RE.findall(read_text(slug, path)))
    except (FileNotFoundError, OSError, ValueError, UnicodeError):
        return 0


def _seed_state() -> BinderState:
    now = utc_now()
    nodes: list[BinderNode] = []
    roots: list[str] = []
    for position, title in enumerate(ROOT_TITLES):
        node_id = _new_id()
        roots.append(node_id)
        nodes.append(
            BinderNode(
                id=node_id,
                title=title,
                kind="trash" if title == "Trash" else "folder",
                position=position,
                include_in_compile=title == "Draft",
                created_at=now,
                updated_at=now,
            )
        )
    return BinderState(roots=roots, nodes=nodes)


def _load_raw(slug: str) -> BinderState | None:
    try:
        payload = json.loads(read_text(slug, BINDER_PATH))
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        return None
    try:
        return BinderState.model_validate(payload)
    except ValueError:
        return None


def _node_map(state: BinderState) -> dict[str, BinderNode]:
    return {node.id: node for node in state.nodes}


def _root_by_title(state: BinderState, title: str) -> BinderNode:
    nodes = _node_map(state)
    for node_id in state.roots:
        node = nodes.get(node_id)
        if node and node.title == title:
            return node
    raise ValueError(f"Binder root is missing: {title}")


def _children(state: BinderState, parent_id: str | None) -> list[BinderNode]:
    return sorted(
        (node for node in state.nodes if node.parent_id == parent_id),
        key=lambda item: (item.position, item.title.casefold()),
    )


def _renumber_siblings(state: BinderState, parent_id: str | None) -> None:
    now = utc_now()
    for position, node in enumerate(_children(state, parent_id)):
        if node.position != position:
            node.position = position
            node.updated_at = now


def _folder_for_directory(
    state: BinderState,
    parent_id: str,
    directory_key: str,
    title: str,
) -> BinderNode:
    for node in state.nodes:
        if node.parent_id != parent_id or node.kind != "folder":
            continue
        if node.custom_metadata.get("source_directory") == directory_key:
            return node
    now = utc_now()
    node = BinderNode(
        id=_new_id(),
        title=title,
        kind="folder",
        parent_id=parent_id,
        position=len(_children(state, parent_id)),
        include_in_compile=False,
        custom_metadata={"source_directory": directory_key},
        created_at=now,
        updated_at=now,
    )
    state.nodes.append(node)
    return node


def _classify_file(path: str) -> str:
    top = PurePosixPath(path).parts[0].casefold() if PurePosixPath(path).parts else ""
    if top == "characters":
        return "character"
    if top == "research":
        return "research"
    return "document"


def _parent_for_file(state: BinderState, path: str) -> str:
    parts = list(PurePosixPath(path).parts)
    if not parts:
        return _root_by_title(state, "Research").id

    top = parts[0].casefold()
    if top == "manuscript":
        parent = _root_by_title(state, "Draft")
        directory_parts = parts[1:-1]
        source_prefix = "manuscript"
    elif top == "research":
        parent = _root_by_title(state, "Research")
        directory_parts = parts[1:-1]
        source_prefix = "research"
    elif top in STORY_BIBLE_FOLDERS:
        parent = _root_by_title(state, "Story Bible")
        source_prefix = top
        parent = _folder_for_directory(state, parent.id, top, parts[0].replace("-", " ").title())
        directory_parts = parts[1:-1]
    else:
        parent = _root_by_title(state, "Research")
        directory_parts = parts[:-1]
        source_prefix = ""

    for directory in directory_parts:
        source_prefix = f"{source_prefix}/{directory}".strip("/")
        parent = _folder_for_directory(
            state,
            parent.id,
            source_prefix,
            directory.replace("-", " ").replace("_", " ").title(),
        )
    return parent.id


def _refresh_derived_fields(slug: str, state: BinderState) -> BinderState:
    root = project_root(slug)
    refreshed: list[BinderNode] = []
    for node in state.nodes:
        metadata = dict(node.custom_metadata)
        if node.path:
            exists = (root / node.path).is_file()
            metadata["source_missing"] = not exists
            count = _word_count(slug, node.path) if exists else 0
        else:
            count = 0
        refreshed.append(node.model_copy(update={"word_count": count, "custom_metadata": metadata}))
    return state.model_copy(update={"nodes": refreshed})


def _persistable_state(state: BinderState) -> BinderState:
    nodes: list[BinderNode] = []
    for node in state.nodes:
        metadata = dict(node.custom_metadata)
        metadata.pop("source_missing", None)
        nodes.append(node.model_copy(update={"word_count": 0, "custom_metadata": metadata}))
    return state.model_copy(update={"nodes": nodes})


def _save_state(slug: str, state: BinderState) -> BinderState:
    durable = _persistable_state(state)
    save_text(slug, BINDER_PATH, json.dumps(durable.model_dump(), indent=2, ensure_ascii=False))
    return _refresh_derived_fields(slug, durable)


def sync_binder(slug: str, state: BinderState | None = None) -> BinderState:
    if not project_root(slug).exists():
        raise FileNotFoundError(slug)
    state = state or _load_raw(slug) or _seed_state()
    tracked = {node.path.casefold(): node for node in state.nodes if node.path}
    now = utc_now()

    for path in get_project(slug)["files"]:
        if path in SKIPPED_FILES or path.startswith(".ember/"):
            continue
        if path.casefold() in tracked:
            continue
        parent_id = _parent_for_file(state, path)
        state.nodes.append(
            BinderNode(
                id=_new_id(),
                title=_file_title(slug, path),
                kind=_classify_file(path),
                parent_id=parent_id,
                position=len(_children(state, parent_id)),
                path=path,
                include_in_compile=path.startswith("manuscript/"),
                created_at=now,
                updated_at=now,
            )
        )
        tracked[path.casefold()] = state.nodes[-1]

    for parent_id in {node.parent_id for node in state.nodes}:
        _renumber_siblings(state, parent_id)
    return _save_state(slug, state)


def get_binder(slug: str) -> BinderState:
    state = _load_raw(slug)
    if state is None:
        return sync_binder(slug)
    return _refresh_derived_fields(slug, state)


def _require_node(state: BinderState, node_id: str) -> BinderNode:
    for node in state.nodes:
        if node.id == node_id:
            return node
    raise FileNotFoundError(node_id)


def _validate_parent(state: BinderState, parent_id: str | None) -> None:
    if parent_id is None:
        return
    parent = _require_node(state, parent_id)
    if parent.kind not in {"folder", "trash"}:
        raise ValueError("Binder parent must be a folder")


def _descendant_ids(state: BinderState, node_id: str) -> set[str]:
    descendants: set[str] = set()
    frontier = [node_id]
    while frontier:
        current = frontier.pop()
        for child in state.nodes:
            if child.parent_id == current and child.id not in descendants:
                descendants.add(child.id)
                frontier.append(child.id)
    return descendants


def _validate_move(state: BinderState, node_id: str, parent_id: str | None) -> None:
    if node_id in state.roots:
        raise ValueError("Binder root nodes cannot be moved")
    if parent_id is None:
        raise ValueError("Non-root Binder nodes must have a parent")
    _validate_parent(state, parent_id)
    if parent_id == node_id:
        raise ValueError("A Binder node cannot contain itself")
    if parent_id in _descendant_ids(state, node_id):
        raise ValueError("A Binder node cannot move beneath one of its descendants")


def _area_for_parent(state: BinderState, parent_id: str | None, kind: str) -> str:
    if kind == "character":
        return "characters"
    if kind == "location":
        return "world/locations"
    if kind == "research":
        return "research"

    if parent_id:
        current = _require_node(state, parent_id)
        while current.parent_id is not None:
            current = _require_node(state, current.parent_id)
        if current.title == "Draft":
            return "manuscript"
        if current.title == "Research":
            return "research"
    return "notes"


def _path_slug(title: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", title.strip().lower()).strip("-")
    return value or f"untitled-{uuid4().hex[:8]}"


def _unique_markdown_path(slug: str, directory: str, title: str) -> str:
    root = project_root(slug)
    stem = _path_slug(title)
    candidate = f"{directory}/{stem}.md"
    suffix = 2
    while (root / candidate).exists():
        candidate = f"{directory}/{stem}-{suffix}.md"
        suffix += 1
    return candidate


def create_node(slug: str, payload: BinderNodeCreate) -> BinderState:
    state = get_binder(slug)
    parent_id = payload.parent_id
    if parent_id is None:
        if payload.kind == "document":
            parent_id = _root_by_title(state, "Draft").id
        elif payload.kind == "research":
            parent_id = _root_by_title(state, "Research").id
        else:
            parent_id = _root_by_title(state, "Story Bible").id
    _validate_parent(state, parent_id)

    path = payload.path
    if payload.kind not in {"folder", "trash"} and not path:
        directory = _area_for_parent(state, parent_id, payload.kind)
        path = _unique_markdown_path(slug, directory, payload.title)
        save_text(slug, path, f"# {payload.title.strip()}\n\n")
    elif path:
        root = project_root(slug)
        if not (root / path).exists():
            save_text(slug, path, f"# {payload.title.strip()}\n\n")

    now = utc_now()
    state.nodes.append(
        BinderNode(
            id=_new_id(),
            title=payload.title.strip(),
            kind=payload.kind,
            parent_id=parent_id,
            position=len(_children(state, parent_id)),
            path=path,
            synopsis=payload.synopsis,
            label=payload.label,
            status=payload.status,
            keywords=payload.keywords,
            include_in_compile=payload.include_in_compile,
            target_words=payload.target_words,
            custom_metadata=payload.custom_metadata,
            created_at=now,
            updated_at=now,
        )
    )
    return _save_state(slug, state)


def update_node(slug: str, node_id: str, payload: BinderNodeUpdate) -> BinderState:
    state = get_binder(slug)
    node = _require_node(state, node_id)
    fields = payload.model_fields_set
    old_parent = node.parent_id
    if "parent_id" in fields:
        _validate_move(state, node_id, payload.parent_id)
        node.parent_id = payload.parent_id
    for field in (
        "title",
        "synopsis",
        "label",
        "status",
        "keywords",
        "include_in_compile",
        "target_words",
        "custom_metadata",
    ):
        if field not in fields:
            continue
        value = getattr(payload, field)
        if field == "title" and isinstance(value, str):
            value = value.strip()
        setattr(node, field, value)
    node.updated_at = utc_now()
    _renumber_siblings(state, old_parent)
    _renumber_siblings(state, node.parent_id)
    return _save_state(slug, state)


def reorder_nodes(slug: str, payload: BinderReorderRequest) -> BinderState:
    state = get_binder(slug)
    _validate_parent(state, payload.parent_id)
    current = _children(state, payload.parent_id)
    current_ids = [node.id for node in current]
    if set(current_ids) != set(payload.node_ids) or len(current_ids) != len(payload.node_ids):
        raise ValueError("Reorder must include every sibling exactly once")
    now = utc_now()
    positions = {node_id: position for position, node_id in enumerate(payload.node_ids)}
    for node in current:
        node.position = positions[node.id]
        node.updated_at = now
    return _save_state(slug, state)


def trash_node(slug: str, node_id: str) -> BinderState:
    state = get_binder(slug)
    node = _require_node(state, node_id)
    if node_id in state.roots:
        raise ValueError("Binder root nodes cannot be trashed")
    trash = _root_by_title(state, "Trash")
    if node.parent_id == trash.id:
        return _refresh_derived_fields(slug, state)
    old_parent = node.parent_id
    node.previous_parent_id = old_parent
    node.parent_id = trash.id
    node.position = len(_children(state, trash.id))
    node.updated_at = utc_now()
    _renumber_siblings(state, old_parent)
    return _save_state(slug, state)


def restore_node(slug: str, node_id: str) -> BinderState:
    state = get_binder(slug)
    node = _require_node(state, node_id)
    trash = _root_by_title(state, "Trash")
    if node.parent_id != trash.id:
        raise ValueError("Node is not in Trash")
    target = node.previous_parent_id
    if target is None or target not in _node_map(state):
        target = _root_by_title(state, "Draft").id
    _validate_parent(state, target)
    node.parent_id = target
    node.previous_parent_id = None
    node.position = len(_children(state, target))
    node.updated_at = utc_now()
    _renumber_siblings(state, trash.id)
    return _save_state(slug, state)


def create_collection(slug: str, payload: BinderCollectionCreate) -> BinderState:
    state = get_binder(slug)
    node_ids = set(_node_map(state))
    if any(node_id not in node_ids for node_id in payload.node_ids):
        raise ValueError("Collection contains an unknown Binder node")
    now = utc_now()
    state.collections.append(
        BinderCollection(
            id=_new_id(),
            name=payload.name.strip(),
            node_ids=list(dict.fromkeys(payload.node_ids)),
            query=payload.query.strip(),
            created_at=now,
            updated_at=now,
        )
    )
    return _save_state(slug, state)


def update_collection(
    slug: str,
    collection_id: str,
    payload: BinderCollectionUpdate,
) -> BinderState:
    state = get_binder(slug)
    collection = next((item for item in state.collections if item.id == collection_id), None)
    if collection is None:
        raise FileNotFoundError(collection_id)
    fields = payload.model_fields_set
    if "node_ids" in fields and payload.node_ids is not None:
        known = set(_node_map(state))
        if any(node_id not in known for node_id in payload.node_ids):
            raise ValueError("Collection contains an unknown Binder node")
        collection.node_ids = list(dict.fromkeys(payload.node_ids))
    if "name" in fields and payload.name is not None:
        collection.name = payload.name.strip()
    if "query" in fields and payload.query is not None:
        collection.query = payload.query.strip()
    collection.updated_at = utc_now()
    return _save_state(slug, state)
