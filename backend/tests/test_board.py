from pathlib import Path

import pytest

from app import board, project_history, storage
from app.board_models import BoardItemCreate, BoardItemUpdate


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def test_board_items_persist_positions_per_project(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    first = storage.create_project("First Novel")
    second = storage.create_project("Second Novel")

    item = board.create_item(
        first["slug"],
        BoardItemCreate(
            kind="sticky",
            title="Third-act reveal",
            body="The witness recognizes the ring.",
            x=412,
            y=266,
            width=300,
            height=210,
        ),
    )
    board.update_item(first["slug"], item.id, BoardItemUpdate(x=518, y=341))

    reloaded = board.load_board(first["slug"])
    assert len(reloaded.items) == 1
    assert reloaded.items[0].title == "Third-act reveal"
    assert reloaded.items[0].x == 518
    assert reloaded.items[0].y == 341
    assert board.load_board(second["slug"]).items == []

    board_file = storage.project_root(first["slug"]) / "planning" / "corkboard.json"
    assert board_file.is_file()
    assert not (storage.project_root(second["slug"]) / "planning" / "corkboard.json").exists()


def test_uploaded_board_asset_is_owned_by_manuscript(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    first = storage.create_project("Image Board")
    second = storage.create_project("Other Book")
    image_bytes = b"\x89PNG\r\n\x1a\nreference-image"

    item = board.store_asset(
        first["slug"],
        filename="castle-reference.png",
        content=image_bytes,
        content_type="image/png",
        x=80,
        y=120,
    )
    assert item.kind == "image"
    assert item.asset_path.startswith("assets/board/")
    assert board.board_asset_path(first["slug"], item.asset_path).read_bytes() == image_bytes

    with pytest.raises(FileNotFoundError):
        board.board_asset_path(second["slug"], item.asset_path)
    with pytest.raises(ValueError):
        board.board_asset_path(first["slug"], "../project.json")


def test_project_checkpoint_restores_board_reference_and_preserved_asset(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Board Recovery")
    slug = project["slug"]
    item = board.store_asset(
        slug,
        filename="notes.pdf",
        content=b"%PDF-1.4 board reference",
        content_type="application/pdf",
    )
    asset = board.board_asset_path(slug, item.asset_path)
    checkpoint = project_history.create_project_checkpoint(slug, "Board arranged")

    board.delete_item(slug, item.id)
    assert asset.exists()
    assert board.load_board(slug).items == []

    project_history.restore_project_checkpoint(slug, checkpoint["id"])
    restored = board.load_board(slug)
    assert [entry.id for entry in restored.items] == [item.id]
    assert board.board_asset_path(slug, restored.items[0].asset_path).read_bytes().startswith(b"%PDF")


def test_board_rejects_empty_and_oversize_uploads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    use_temp_data(tmp_path)
    project = storage.create_project("Board Limits")

    with pytest.raises(ValueError, match="empty"):
        board.store_asset(
            project["slug"],
            filename="empty.txt",
            content=b"",
            content_type="text/plain",
        )

    monkeypatch.setattr(board, "BOARD_ASSET_LIMIT", 8)
    with pytest.raises(ValueError, match="50 MB"):
        board.store_asset(
            project["slug"],
            filename="huge.bin",
            content=b"012345678",
            content_type="application/octet-stream",
        )
