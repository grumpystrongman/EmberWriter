from fastapi.testclient import TestClient

from app.main import app


def test_stable_diffusion_502_is_actionable() -> None:
    @app.get("/__test_sd_502")
    def _raise_sd_error():
        from fastapi import HTTPException

        raise HTTPException(status_code=502, detail="Stable Diffusion server error: All connection attempts failed")

    response = TestClient(app).get("/__test_sd_502")
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "image-server status control" in detail
    assert "--api" in detail
    assert "Docker/WSL" in detail
