from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_normal_project_list_does_not_launch_forensic_recovery() -> None:
    main = (REPO_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    projects_route = main.split('@app.get("/api/projects", response_model=list[ProjectSummary])', 1)[1]
    projects_route = projects_route.split('@app.get("/api/projects/recovery-status")', 1)[0]

    assert "return list_projects()" in projects_route
    assert "_run_project_recovery()" not in projects_route


def test_windows_start_waits_for_backend_health_before_opening_browser() -> None:
    start = (REPO_ROOT / "start.ps1").read_text(encoding="utf-8")

    assert '$ApiUrl = "http://127.0.0.1:8000/api/health"' in start
    assert "Invoke-RestMethod -Uri $ApiUrl" in start
    assert "Wait-ForService -Process $BackendProcess" in start
    assert "-RedirectStandardOutput $BackendOutLog" in start
    assert "-RedirectStandardError $BackendErrLog" in start
    assert "EmberWriter API failed to become healthy on port 8000" in start
    assert start.index("Wait-ForService -Process $BackendProcess") < start.index("Start-Process $UiUrl")


def test_windows_start_prefers_projects_in_current_checkout_over_stale_environment() -> None:
    start = (REPO_ROOT / "start.ps1").read_text(encoding="utf-8")

    assert "if (Test-ProjectDataRoot $DefaultDataRoot)" in start
    assert "instead of stale EMBER_DATA_DIR" in start
    assert "$env:EMBER_DATA_DIR = $DefaultDataRoot" in start
    assert '[string]$DataDir = ""' in start


def test_windows_start_repairs_incomplete_frontend_dependencies() -> None:
    start = (REPO_ROOT / "start.ps1").read_text(encoding="utf-8")
    install = (REPO_ROOT / "install.ps1").read_text(encoding="utf-8")

    assert 'node_modules\\.bin\\vite.cmd' in start
    assert "function Test-FrontendDependencies" in start
    assert "function Repair-FrontendDependencies" in start
    assert "npm ls --depth=0 --include=dev" in start
    assert "ci --include=dev" in start
    assert "Frontend dependencies repaired; Vite is available." in start
    assert "npm ci --include=dev" in install
    assert 'node_modules\\.bin\\vite.cmd' in install


def test_vite_uses_strict_local_port_and_same_origin_api_proxy() -> None:
    vite = (REPO_ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")

    assert "const DEV_API_BASE = '/api'" in vite
    assert "strictPort: true" in vite
    assert "target: 'http://127.0.0.1:8000'" in vite
