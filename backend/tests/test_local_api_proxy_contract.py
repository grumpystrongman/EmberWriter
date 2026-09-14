from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_local_vite_dev_server_proxies_api_to_backend() -> None:
    vite_config = (REPO_ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")

    assert "const DEV_API_BASE = '/api'" in vite_config
    assert "mode === 'development' ? DEV_API_BASE : LOCAL_API_BASE" in vite_config
    assert "proxy:" in vite_config
    assert "'/api':" in vite_config
    assert "target: 'http://127.0.0.1:8000'" in vite_config
