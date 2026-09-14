import base64
import io
from pathlib import Path

import pytest
from PIL import Image
from starlette.datastructures import Headers, UploadFile

from app import routes_media, storage
from app.media_models import (
    VisualAssetGenerateRequest,
    VisualAssetUpdate,
    VisualPromptRequest,
)
from app.models import ProviderConfig


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def image_bytes(size: tuple[int, int] = (640, 480)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (50, 65, 80)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_visual_asset_upload_metadata_and_canon_round_trip(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Visual Novel")["slug"]
    upload = UploadFile(
        filename="blackwood.png",
        file=io.BytesIO(image_bytes()),
        headers=Headers({"content-type": "image/png"}),
    )

    asset = await routes_media.upload_visual_asset(
        slug, "blackwood", upload, title="Blackwood", kind="location"
    )
    assert asset["canon_status"] == "reference"
    assert asset["relative_path"] == "assets/visuals/blackwood.png"
    assert len(routes_media.list_visual_assets(slug)) == 1

    updated = routes_media.update_visual_asset_metadata(
        slug,
        "blackwood",
        VisualAssetUpdate(
            canon_status="canonical",
            linked_entities=["Blackwood"],
            notes="Approved exterior reference.",
        ),
    )
    assert updated["canon_status"] == "canonical"
    assert updated["linked_entities"] == ["Blackwood"]
    assert routes_media.visual_asset_metadata(slug, "blackwood")["notes"].startswith(
        "Approved"
    )

    routes_media.delete_visual_asset(slug, "blackwood")
    assert routes_media.list_visual_assets(slug) == []


@pytest.mark.asyncio
async def test_visual_generation_supports_canonical_img2img_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Reference Novel")["slug"]
    reference_upload = UploadFile(
        filename="temple.png",
        file=io.BytesIO(image_bytes((512, 512))),
        headers=Headers({"content-type": "image/png"}),
    )
    await routes_media.upload_visual_asset(
        slug,
        "temple-reference",
        reference_upload,
        title="Temple",
        kind="location",
    )

    encoded = base64.b64encode(image_bytes((768, 512))).decode("ascii")
    captured: dict = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"images": [encoded]}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def post(self, url: str, json: dict):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(
        routes_media.httpx, "AsyncClient", lambda *args, **kwargs: FakeClient()
    )

    result = await routes_media.generate_visual_asset(
        slug,
        VisualAssetGenerateRequest(
            asset_id="temple-rain",
            title="Temple in Rain",
            prompt="same ruined temple during a thunderstorm",
            reference_asset_id="temple-reference",
            denoising_strength=0.35,
        ),
    )
    assert captured["url"].endswith("/sdapi/v1/img2img")
    assert captured["json"]["init_images"]
    assert captured["json"]["denoising_strength"] == 0.35
    assert result["reference_asset_id"] == "temple-reference"
    assert result["width"] == 768


@pytest.mark.asyncio
async def test_visual_prompt_composition_is_structured_and_source_aware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Prompt Novel")["slug"]
    storage.save_text(
        slug,
        "world/redwater.md",
        "# Redwater\nA three-arch imperial stone bridge crosses a glacial river.",
    )

    async def fake_generate(*_args, **_kwargs) -> str:
        return (
            '{"prompt":"three-arch imperial stone bridge over a glacial river, storm light",'
            '"negative_prompt":"modern concrete, suspension bridge",'
            '"continuity_notes":["The bridge material and arch count are established canon."]}'
        )

    monkeypatch.setattr(routes_media, "generate", fake_generate)
    response = await routes_media.compose_visual_prompt(
        slug,
        VisualPromptRequest(
            subject="Redwater",
            kind="location",
            instruction="Show the crossing just before the battle.",
            provider=ProviderConfig(model="test"),
        ),
    )
    assert "three-arch" in response.prompt
    assert "world/redwater.md" in response.context_sources
    assert response.continuity_notes
