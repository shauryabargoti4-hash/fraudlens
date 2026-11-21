from pathlib import Path
from backend.core.config import Settings


def test_settings_defaults():
    settings = Settings(
        app_name="ClauseGuard-Test",
        database_url="sqlite:///:memory:",
    )
    assert settings.app_name == "ClauseGuard-Test"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.high_risk_threshold == 70.0
    assert settings.medium_risk_threshold == 40.0
    assert isinstance(settings.allowed_origins, list)
    assert len(settings.allowed_origins) > 0


def test_settings_json_parsing():
    settings = Settings(
        allowed_origins='["http://example.com", "http://test.local"]',
        allowed_extensions="pdf, png, jpg",
    )
    assert "http://example.com" in settings.allowed_origins
    assert "http://test.local" in settings.allowed_origins
    assert "pdf" in settings.allowed_extensions
    assert "png" in settings.allowed_extensions


def test_ensure_directories(tmp_path: Path):
    storage = tmp_path / "storage"
    uploads = storage / "uploads"
    chroma = storage / "chroma"

    settings = Settings(
        storage_dir=storage,
        upload_dir=uploads,
        chroma_dir=chroma,
    )
    settings.ensure_directories()
    assert storage.exists()
    assert uploads.exists()
    assert chroma.exists()
