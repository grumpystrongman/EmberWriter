import io
from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image
from starlette.datastructures import Headers, UploadFile

from app import routes_atlas, routes_media, storage
from app.atlas_models import AtlasLocation, StoryAtlas


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def upload_file() -> UploadFile:
    buffer = io.BytesIO()
    Image.new("RGB", (320, 240), (40, 55, 70)).save(buffer, format="PNG")
    buffer.seek(0)
    return UploadFile(
        filename="place.png",
        file=buffer,
        headers=Headers({"content-type": "image/png"}),
    )


@pytest.mark.asyncio
async def test_atlas_visual_reference_must_exist_and_blocks_asset_deletion(
    tmp_path: Path,
) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Atlas Visual Integrity")["slug"]

    missing = StoryAtlas(
        locations=[
            AtlasLocation(
                id="redwater",
                name="Redwater",
                image_asset_id="missing-reference",
            )
        ]
    )
    with pytest.raises(HTTPException) as exc_info:
        routes_atlas.put_atlas(slug, missing)
    assert exc_info.value.status_code == 400
    assert "missing visual asset" in str(exc_info.value.detail)

    await routes_media.upload_visual_asset(
        slug,
        "redwater-reference",
        upload_file(),
        title="Redwater",
        kind="location",
    )
    saved = routes_atlas.put_atlas(
        slug,
        StoryAtlas(
            locations=[
                AtlasLocation(
                    id="redwater",
                    name="Redwater",
                    image_asset_id="redwater-reference",
                )
            ]
        ),
    )
    assert saved.locations[0].image_asset_id == "redwater-reference"

    with pytest.raises(HTTPException) as exc_info:
        routes_media.delete_visual_asset(slug, "redwater-reference")
    assert exc_info.value.status_code == 409
    assert "atlas:location:redwater" in str(exc_info.value.detail)

    routes_atlas.put_atlas(
        slug,
        StoryAtlas(locations=[AtlasLocation(id="redwater", name="Redwater")]),
    )
    routes_media.delete_visual_asset(slug, "redwater-reference")
    assert routes_media.list_visual_assets(slug) == []
