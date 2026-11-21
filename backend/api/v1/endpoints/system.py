import shutil
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text, select, func
from sqlalchemy.orm import Session
from backend import __version__
from backend.core.config import get_settings, Settings
from backend.core.database import get_db
from backend.models.policy import Policy
from backend.models.claim import Claim
from backend.models.finding import DiscrepancyFinding
from backend.schemas.system import HealthCheckResponse, SystemStatusResponse, ComponentStatus

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse, summary="Service Health Check")
def get_health(settings: Settings = Depends(get_settings)) -> HealthCheckResponse:
    """Returns quick health verification for container orchestrators and monitoring probes."""
    return HealthCheckResponse(
        status="healthy",
        app_name=settings.app_name,
        version=__version__,
        environment=settings.app_env,
    )


@router.get("/system/status", response_model=SystemStatusResponse, summary="Detailed System Status")
def get_system_status(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SystemStatusResponse:
    """Performs deep health check across database, local file storage, and AI service configuration."""
    # 1. Check Database
    try:
        db.execute(text("SELECT 1"))
        db_status = ComponentStatus(name="database", status="healthy", details="SQLite connected")
    except Exception as e:
        db_status = ComponentStatus(name="database", status="degraded", details=str(e))

    # 2. Check Storage
    try:
        settings.ensure_directories()
        free_bytes = shutil.disk_usage(settings.storage_dir).free
        free_mb = round(free_bytes / (1024 * 1024), 2)
        storage_status = ComponentStatus(
            name="storage",
            status="healthy",
            details=f"Directory writable. Free space: {free_mb} MB",
        )
    except Exception as e:
        storage_status = ComponentStatus(name="storage", status="degraded", details=str(e))

    # 3. Check LLM Provider Config
    if settings.llm_provider == "gemini":
        llm_detail = "Gemini configured" if settings.has_gemini_api_key else "Gemini provider selected (no API key configured; running in mock/offline mode)"
        llm_status = ComponentStatus(
            name="llm_provider",
            status="healthy" if settings.has_gemini_api_key else "offline_fallback",
            details=llm_detail,
        )
    else:
        llm_status = ComponentStatus(
            name="llm_provider",
            status="healthy",
            details=f"Provider: {settings.llm_provider}",
        )

    # 4. Check Embedding Provider Config
    embedding_status = ComponentStatus(
        name="embedding_provider",
        status="healthy",
        details=f"Provider: {settings.embedding_provider}",
    )

    # 5. Check OCR Engine Config
    ocr_status = ComponentStatus(
        name="ocr_engine",
        status="healthy" if settings.tesseract_cmd else "auto_detect",
        details="Tesseract binary: " + (settings.tesseract_cmd or "Default PATH / PyMuPDF text fallback"),
    )

    # 6. Gather Entity Counts
    try:
        policy_count = db.scalar(select(func.count(Policy.id))) or 0
        claim_count = db.scalar(select(func.count(Claim.id))) or 0
        finding_count = db.scalar(select(func.count(DiscrepancyFinding.id))) or 0
    except Exception:
        policy_count, claim_count, finding_count = 0, 0, 0

    return SystemStatusResponse(
        status="operational",
        app_name=settings.app_name,
        version=__version__,
        environment=settings.app_env,
        database=db_status,
        storage=storage_status,
        llm_provider=llm_status,
        embedding_provider=embedding_status,
        ocr_engine=ocr_status,
        counts={
            "policies": policy_count,
            "claims": claim_count,
            "findings": finding_count,
        },
    )
