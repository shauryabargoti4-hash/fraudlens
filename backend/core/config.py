import json
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """ClauseGuard application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Base Application
    app_name: str = "ClauseGuard"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_v1_prefix: str = "/api/v1"

    # Security & CORS
    secret_key: str = "clauseguard-development-secret-key-change-in-production"
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]

    # Database
    database_url: str = "sqlite:///./storage/clauseguard.db"
    db_echo: bool = False

    # Storage Paths
    storage_dir: Path = Path("./storage")
    upload_dir: Path = Path("./storage/uploads")
    chroma_dir: Path = Path("./storage/chroma_db")

    # Document Extraction & OCR
    tesseract_cmd: Optional[str] = None
    max_upload_size_mb: float = 25.0
    allowed_extensions: List[str] = ["pdf", "txt", "png", "jpg", "jpeg", "tiff"]

    # AI & Embeddings
    llm_provider: str = "gemini"  # "gemini" or "mock"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-pro"
    gemini_fallback_model: str = "gemini-1.5-flash"
    gemini_temperature: float = 0.2
    gemini_max_output_tokens: int = 2048
    gemini_timeout_seconds: float = 30.0

    embedding_provider: str = "mock"  # "mock" or "gemini"
    embedding_model: str = "text-embedding-004"
    embedding_dimension: int = 768
    embedding_batch_size: int = 32
    chroma_collection_name: str = "clauseguard_policies"

    # Fraud & Risk Engine Thresholds
    high_risk_threshold: float = 70.0
    medium_risk_threshold: float = 40.0
    max_permissible_date_gap_days: int = 180

    @field_validator("allowed_origins", "allowed_extensions", mode="before")
    @classmethod
    def parse_json_list(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_stripped = v.strip()
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    return json.loads(v_stripped)
                except Exception:
                    pass
            # Comma-separated fallback
            return [item.strip() for item in v_stripped.split(",") if item.strip()]
        return v

    def ensure_directories(self) -> None:
        """Create necessary directories if they do not exist."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def has_gemini_api_key(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.strip())


@lru_cache()
def get_settings() -> Settings:
    """Returns cached application settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings
