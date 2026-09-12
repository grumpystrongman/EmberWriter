from __future__ import annotations

import zipfile
from pathlib import Path

from app import binder, previewing, storage
from app.binder_models import BinderNodeCreate, BinderNodeUpdate, BinderReorderRequest


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_preview_uses_binder_compile_order_and_builds_reader_site(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Preview Test")
    slug = project["slug"]
    state = binder.get_binder(slug)
    draft = next(node for node in state.nodes if node.title == "Draft")
    first = next(node for node in state.nodes if node.path == "manuscript/chapter-001.md")
    assert first.path
    storage.save_text(slug, first.path, "# First Scene\n\nThe first preview paragraph.\n")
    state = binder.update_node(slug, first.id, BinderNodeUpdate(title="First Scene"))

    before = {node.id for node in state.nodes}
    state = binder.create_node(
        slug,
        BinderNodeCreate(title="Second Scene", kind="document", parent_id=draft.id),
    )
    second = next(node for node in state.nodes if node.id not in before)
    assert second.path
    storage.save_text(slug, second.path, "# Second Scene\n\nThe second preview paragraph.\n")

    siblings = sorted(
        (node for node in state.nodes if node.parent_id == draft.id),
        key=lambda node: node.position,
    )
    binder.reorder_nodes(
        slug,
        BinderReorderRequest(
            parent_id=draft.id,
            node_ids=[second.id, *[node.id for node in siblings if node.id != second.id]],
        ),
    )

    payload = previewing.preview_payload(
        slug,
        title="The Preview Book",
        author="A. Writer",
        trim_width=6,
        trim_height=9,
    )
    assert payload["documents"][0]["title"] == "Second Scene"
    assert "second preview paragraph" in payload["documents"][0]["html"].lower()
    assert payload["trim_width"] == 6
    assert payload["trim_height"] == 9

    artifact = previewing.build_preview_site(slug, title="The Preview Book", author="A. Writer")
    root = storage.project_root(slug)
    zip_path = root / artifact["relative_path"]
    assert zip_path.is_file()
    assert artifact["documents"] == len(payload["documents"])

    with zipfile.ZipFile(zip_path) as archive:
        assert {"index.html", "README.txt"}.issubset(set(archive.namelist()))
        index = archive.read("index.html").decode("utf-8")
        readme = archive.read("README.txt").decode("utf-8")
    assert "The Preview Book" in index
    assert "Second Scene" in index
    assert "authentication" in readme.lower()
