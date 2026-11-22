"""Tests for ClauseGuard Docker and Docker Compose Configuration."""

from pathlib import Path
import yaml


def test_docker_files_exist():
    assert Path("Dockerfile.backend").exists(), "Dockerfile.backend must exist"
    assert Path("Dockerfile.frontend").exists(), "Dockerfile.frontend must exist"
    assert Path("docker-compose.yml").exists(), "docker-compose.yml must exist"
    assert Path(".dockerignore").exists(), ".dockerignore must exist"


def test_docker_compose_structure():
    compose_path = Path("docker-compose.yml")
    content = compose_path.read_text(encoding="utf-8")
    config = yaml.safe_load(content)

    assert "services" in config, "Compose file must define 'services'"
    services = config["services"]

    # 1. Backend Service Checks
    assert "backend" in services, "Service 'backend' must be defined"
    backend = services["backend"]
    assert "8000:8000" in backend.get("ports", []), "Backend must expose port 8000"

    # Volume persistence for SQLite & ChromaDB
    volumes = backend.get("volumes", [])
    has_storage_mount = any("./storage:/app/storage" in v for v in volumes)
    assert has_storage_mount, "Backend must mount ./storage:/app/storage for SQLite and ChromaDB persistence"

    # Healthcheck configured
    assert "healthcheck" in backend, "Backend must configure a healthcheck probe"
    assert "/health" in str(backend["healthcheck"].get("test", [])), "Backend healthcheck must query /health"

    # 2. Frontend Service Checks
    assert "frontend" in services, "Service 'frontend' must be defined"
    frontend = services["frontend"]
    assert "8501:8501" in frontend.get("ports", []), "Frontend must expose port 8501"

    # Frontend dependency on backend health
    depends_on = frontend.get("depends_on", {})
    assert "backend" in depends_on, "Frontend must depend on backend"
    assert depends_on["backend"].get("condition") == "service_healthy", "Frontend must wait for backend service_healthy"

    # Internal Docker network URL configured
    env_vars = frontend.get("environment", [])
    assert any("CLAUSEGUARD_API_URL=http://backend:8000/api/v1" in e for e in env_vars), \
        "Frontend must point to internal backend URL http://backend:8000/api/v1"

    # 3. Networks
    assert "networks" in config, "Compose must define a bridge network"
    assert "clauseguard-net" in config["networks"]


def test_dockerignore_excludes_sensitive_and_local_artifacts():
    dockerignore = Path(".dockerignore").read_text(encoding="utf-8")
    lines = [line.strip() for line in dockerignore.splitlines() if line.strip() and not line.startswith("#")]

    assert any(".venv" in l for l in lines), ".dockerignore must exclude .venv"
    assert any(".git" in l for l in lines), ".dockerignore must exclude .git"
    assert any(".env" in l for l in lines), ".dockerignore must exclude .env"
    assert any("__pycache__" in l for l in lines), ".dockerignore must exclude __pycache__"


def test_no_hardcoded_developer_paths_or_secrets():
    files_to_check = [
        Path("docker-compose.yml"),
        Path("Dockerfile.backend"),
        Path("Dockerfile.frontend"),
        Path(".env.example"),
    ]

    for p in files_to_check:
        text = p.read_text(encoding="utf-8")
        assert "C:\\" not in text, f"Hardcoded Windows path detected in {p}"
        assert "/Users/" not in text, f"Hardcoded developer path detected in {p}"
        assert "AIza" not in text, f"Potential real Gemini API key detected in {p}"
        assert "sk-" not in text, f"Potential API secret detected in {p}"
