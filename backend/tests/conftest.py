"""Cross-platform synthetic Windows-SAPI test support.

Several audiobook contract tests already mock subprocess-based Windows narration
to produce fake WAV bytes. Their platform check must be mocked as well when CI
runs on Linux; otherwise tests never reach the synthetic renderer. This fixture
changes only the two imported app modules' `sys` references and only for the
specified synthetic contract tests. Production Windows-only behavior is intact.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

_SYNTHETIC_SAPI_MODULES = {
    "test_audio_drama_local.py",
    "test_audio_production.py",
    "test_audiobook_jobs.py",
    "test_audiobook_local.py",
    "test_audiobook_quality.py",
    "test_release_proof_cast_noise.py",
}


@pytest.fixture(autouse=True)
def fake_windows_for_mocked_sapi_contracts(request: pytest.FixtureRequest,
                                          monkeypatch: pytest.MonkeyPatch):
    if sys.platform == "win32" or request.node.path.name not in _SYNTHETIC_SAPI_MODULES:
        return
    from app import audiobook_jobs, audiobook_local

    # Never patch the process-wide real sys module: third-party libraries and
    # asyncio need the actual OS platform to work correctly.
    synthetic_sys = SimpleNamespace(platform="win32")
    monkeypatch.setattr(audiobook_jobs, "sys", synthetic_sys)
    monkeypatch.setattr(audiobook_local, "sys", synthetic_sys)
