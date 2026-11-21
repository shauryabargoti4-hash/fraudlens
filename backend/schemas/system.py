import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ComponentStatus(BaseModel):
    name: str
    status: str  # "healthy", "degraded", "unavailable"
    details: Optional[str] = None


class HealthCheckResponse(BaseModel):
    status: str = "healthy"
    app_name: str
    version: str
    environment: str
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class SystemStatusResponse(BaseModel):
    status: str = "operational"
    app_name: str
    version: str
    environment: str
    database: ComponentStatus
    storage: ComponentStatus
    llm_provider: ComponentStatus
    embedding_provider: ComponentStatus
    ocr_engine: ComponentStatus
    counts: Dict[str, int]
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
