from typing import Optional
from pydantic import Field
from backend.models.enums import FindingType, FindingSeverity, RecommendationType
from backend.schemas.common import BaseSchema, TimestampedSchema


class FindingBase(BaseSchema):
    finding_type: FindingType
    severity: FindingSeverity = FindingSeverity.MEDIUM
    title: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=5)
    evidence_snippet: Optional[str] = None
    policy_reference: Optional[str] = None
    suggested_action: Optional[str] = None
    is_verified_by_human: bool = False


class FindingCreate(FindingBase):
    claim_id: int


class FindingResponse(FindingBase, TimestampedSchema):
    claim_id: int


class AnalysisReportBase(BaseSchema):
    overall_risk_score: float = Field(..., ge=0.0, le=100.0)
    recommendation: RecommendationType
    confidence_score: float = Field(1.0, ge=0.0, le=1.0)
    executive_summary: str = Field(..., min_length=5)
    findings_count: int = Field(0, ge=0)
    loophole_analysis: Optional[str] = None
    agent_trace: Optional[dict] = Field(default_factory=dict)


class AnalysisReportCreate(AnalysisReportBase):
    claim_id: int


class AnalysisReportResponse(AnalysisReportBase, TimestampedSchema):
    claim_id: int
