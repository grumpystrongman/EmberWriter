from pathlib import Path
import io

import pytest
from PIL import Image
from starlette.datastructures import Headers, UploadFile

from app import routes_visual_interpret, routes_media, storage
from app.routes_visual_interpret import ImageInterpretRequest


@pytest.mark.asyncio
async def test_vision_reference_is_local_and_cannot_change_canon(tmp_path: Path, monkeypatch):
    storage.DATA_ROOT = tmp_path
    storage.PROJECTS_ROOT = tmp_path / "projects"
    slug = storage.create_project("Visual Thinking")["slug"]
    pixels = io.BytesIO()
    Image.new("RGB", (40, 40), (60, 90, 120)).save(pixels, format="PNG")
    await routes_media.upload_visual_asset(
        slug, "castle", UploadFile(file=io.BytesIO(pixels.getvalue()),
            filename="castle.png", headers=Headers({"content-type": "image/png"})),
        title="Castle", kind="reference", source_url="",
    )
    observed = {}

    class Response:
        def raise_for_status(self): pass
        def json(self): return {"message": {"content": "What I see: stone walls."}}

    class Client:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): return None
        async def post(self, url, json):
            observed["url"] = url
            observed["body"] = json
            return Response()

    monkeypatch.setattr(routes_visual_interpret.httpx, "AsyncClient", Client)
    response = await routes_visual_interpret.interpret_visual_reference(
        slug, "castle", ImageInterpretRequest(model="local-vision", direction="Notice the mood"))
    assert observed["url"] == "http://127.0.0.1:11434/api/chat"
    assert observed["body"]["messages"][-1]["images"]
    assert response["applied_to_manuscript"] is False
    assert routes_media.visual_asset_metadata(slug, "castle")["canon_status"] == "reference"
    assert "stone walls" in response["interpretation"]
