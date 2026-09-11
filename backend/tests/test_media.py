import base64
import io
from pathlib import Path

import pytest
from PIL import Image
from starlette.datastructures import Headers, UploadFile

from app import routes_media, storage
from app.media_models import CharacterPortraitGenerateRequest


def use_temp_data(tmp_path: Path) -> None:
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"


def image_bytes(size: tuple[int, int] = (240, 320)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (48, 72, 96)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_character_portrait_upload_round_trip(tmp_path: Path) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Portrait Novel")["slug"]
    raw = image_bytes()
    upload = UploadFile(
        filename="mara.png",
        file=io.BytesIO(raw),
        headers=Headers({"content-type": "image/png"}),
    )

    result = await routes_media.upload_portrait(slug, "Mara Vale", upload)

    assert result["source"] == "upload"
    assert result["relative_path"] == "characters/assets/mara-vale.png"
    assert result["width"] == 240
    assert result["height"] == 320
    assert (storage.project_root(slug) / result["relative_path"]).exists()

    metadata = routes_media.portrait_metadata(slug, "Mara Vale")
    assert metadata["character"] == "Mara Vale"
    response = routes_media.portrait_image(slug, "Mara Vale")
    assert Path(response.path).name == "mara-vale.png"

    routes_media.delete_portrait(slug, "Mara Vale")
    assert not (storage.project_root(slug) / result["relative_path"]).exists()


@pytest.mark.asyncio
async def test_character_portrait_generation_uses_stable_diffusion_webui(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_temp_data(tmp_path)
    slug = storage.create_project("Generated Portrait")["slug"]
    encoded = base64.b64encode(image_bytes((384, 512))).decode("ascii")
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

    monkeypatch.setattr(routes_media.httpx, "AsyncClient", lambda *args, **kwargs: FakeClient())

    result = await routes_media.generate_portrait(
        slug,
        CharacterPortraitGenerateRequest(
            character="Jax",
            prompt="adult woman, scarred fighter, cinematic dark fantasy portrait",
            base_url="http://127.0.0.1:7860",
            width=512,
            height=768,
            steps=24,
        ),
    )

    assert captured["url"] == "http://127.0.0.1:7860/sdapi/v1/txt2img"
    assert captured["json"]["steps"] == 24
    assert result["source"] == "stable_diffusion_webui"
    assert result["prompt"].startswith("adult woman")
    assert result["width"] == 384
    assert result["height"] == 512
    assert (storage.project_root(slug) / "characters/assets/jax.png").exists()
