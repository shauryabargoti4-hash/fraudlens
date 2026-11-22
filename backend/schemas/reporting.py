"""Reporting and Batch Audit Schemas for ClauseGuard."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from backend.models.enums import AdvisoryVerdict, RecommendationType, UserRole


class ReportOverrideRequest(BaseModel):
    """Payload for senior adjudicator verdict override and digital sign-off."""

    final_verdict: AdvisoryVerdict = Field(
        ..., description="Final adjudicated verdict (TAKE, REVIEW_REQUIRED, or DO_NOT_TAKE)"
    )
    adjudicator_name: str = Field(..., min_length=2, max_length=150, description="Full name of the senior adjudicator")
    justification: str = Field(..., min_length=5, description="Clear business or legal rationale for the override")


class ReportOverrideResponse(BaseModel):
    """Confirmation response for recorded digital sign-off and verdict override."""

    status: str = "success"
    report_id: int
    claim_id: int
    original_verdict: str
    final_verdict: str
    adjudicator_name: str
    justification: str
    timestamp: str


class BatchClaimAuditRequest(BaseModel):
    """Payload for multi-claim portfolio batch auditing."""

    claim_ids: Optional[List[int]] = Field(None, description="Explicit list of claim IDs to audit in batch")
    policy_id: Optional[int] = Field(None, description="Optional target policy ID to audit all associated claims")


class BatchClaimItemResult(BaseModel):
    """Per-claim outcome within a batch audit execution."""

    claim_id: int
    claim_number: Optional[str] = None
    status: str  # "success" or "error"
    verdict: Optional[str] = None
    risk_score: Optional[float] = None
    report_id: Optional[int] = None
    error_message: Optional[str] = None


class BatchClaimAuditResponse(BaseModel):
    """Aggregate response summarizing multi-claim portfolio batch audit."""

    total_claims: int
    processed_count: int
    successful_count: int
    failed_count: int
    verdict_counts: Dict[str, int] = Field(default_factory=dict)
    results: List[BatchClaimItemResult] = Field(default_factory=list)
