"""Pinokio script contract checks without pretending an installed Pinokio host was tested.

These validate Windows-only low-footprint installer intent, script syntax and
user-data persistence. A real Pinokio first-run remains a separate release
gate on a freshly installed machine.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _node() -> str:
    executable = shutil.which("node")
    if not executable:
        pytest.skip("Node is not installed on this backend-only test runner")
    return executable


def _node_eval(js: str) -> dict:
    script = subprocess.run([_node(), "-e", js], cwd=ROOT,
                            capture_output=True, text=True, timeout=15, check=True)
    return json.loads(script.stdout)


@pytest.mark.parametrize("path", ["pinokio.js", "pinokio-install.js", "pinokio-start.js"])
def test_pinokio_javascript_parses(path):
    subprocess.run([_node(), "--check", str(ROOT / path)],
                   cwd=ROOT, check=True, capture_output=True, timeout=15)


def test_pinokio_launcher_menu_does_not_autoinstall_or_delete_data():
    result = _node_eval("""
const launcher = require('./pinokio.js');
Promise.all([
 launcher.menu({}, {exists: () => false, running: () => false}),
 launcher.menu({}, {exists: () => true, running: () => false}),
 launcher.menu({}, {exists: () => true, running: () => true}),
]).then(items => process.stdout.write(JSON.stringify({
  version: launcher.version, install: items[0], installed: items[1],
  running: items[2]
})));
""")
    assert result["version"] == "8.0.0"
    assert any(item.get("href") == "pinokio-install.js" for item in result["install"])
    assert not any(item.get("default") for item in result["install"])
    assert any(item.get("href") == "pinokio-start.js" for item in result["installed"])
    assert any(item.get("href") == "http://127.0.0.1:5173" for item in result["running"])
    assert not any(item.get("href") == "pinokio-install.js"
                   for item in result["running"] if item.get("default"))


def test_pinokio_install_requires_explicit_user_action_and_no_optional_models():
    install = _node_eval("console.log(JSON.stringify(require('./pinokio-install.js')))")
    assert install["version"] == "8.0.0"
    windows = [part for part in install["run"]
               if part.get("when") == "{{platform === 'win32'}}"]
    assert len(windows) == 1
    command = windows[0]["params"]["message"]
    for argument in ("-SkipModelDownload", "-SkipImageEngineInstall",
                     "-SkipImageModelDownload"):
        assert argument in command
    for dangerous in ("ollama pull", "winget install", "Remove-Item",
                      "rm -rf", "InstallAIModels", "InstallImageEngine"):
        assert dangerous not in command


def test_pinokio_start_guards_ports_and_preserves_author_data():
    start = _node_eval("console.log(JSON.stringify(require('./pinokio-start.js')))")
    assert start["daemon"] is True
    assert start["run"][0]["params"]["message"].endswith("pinokio-launch-windows.ps1")
    script = (ROOT / "scripts/pinokio-launch-windows.ps1").read_text(encoding="utf-8")
    assert "PinokioAuthorData" in script
    assert "$env:LOCALAPPDATA" in script
    assert "Get-NetTCPConnection" in script
    assert "throw \"Port $Port is already in use." in script
    assert script.index("Get-NetTCPConnection") < script.index('start.ps1")')
    assert "Stop-Process" not in script
    assert "Remove-Item" not in script
    assert "-DataDir $DataDir" in script
    assert "5173" in script and "8000" in script


def test_pinokio_metadata_parses_without_auto_download_or_unlicensed_models():
    metadata = json.loads((ROOT / "pinokio.json").read_text(encoding="utf-8"))
    assert "EmberWriter" in metadata["title"]
    assert "source" not in metadata.get("kind", "") or metadata.get("kind") != "release"
