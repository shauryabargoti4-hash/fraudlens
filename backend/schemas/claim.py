import datetime
from typing import List, Optional
from pydantic import Field, model_validator
from backend.models.enums import ClaimStatus, DocumentType
from backend.schemas.common import BaseSchema, TimestampedSchema


class ClaimDocumentBase(BaseSchema):
    filename: str = Field(..., min_length=1, max_length=255)
    file_path: str = Field(..., min_length=1, max_length=500)
    file_hash: str = Field(..., min_length=8, max_length=64)
    document_type: DocumentType = DocumentType.OTHER
    page_count: int = Field(1, ge=1)
    ocr_applied: bool = False
    extracted_text: Optional[str] = None
    extracted_metadata: Optional[dict] = Field(default_factory=dict)


class ClaimDocumentCreate(ClaimDocumentBase):
    pass


class ClaimDocumentResponse(ClaimDocumentBase, TimestampedSchema):
    claim_id: int


class ClaimBase(BaseSchema):
    claim_number: str = Field(..., min_length=3, max_length=100)
    policy_id: int
    claimant_name: str = Field(..., min_length=2, max_length=255)
    incident_date: datetime.date
    filing_date: datetime.date
    claimed_amount: float = Field(..., gt=0.0)
    approved_amount: Optional[float] = Field(None, ge=0.0)
    status: ClaimStatus = ClaimStatus.SUBMITTED
    fraud_risk_score: float = Field(0.0, ge=0.0, le=100.0)
    summary: Optional[str] = None
    fraud_indicators_summary: Optional[str] = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ClaimBase":
        if self.filing_date < self.incident_date:
            raise ValueError("filing_date cannot be earlier than incident_date")
        return self


class ClaimCreate(ClaimBase):
    pass


class ClaimUpdate(BaseSchema):
    claimant_name: Optional[str] = None
    incident_date: Optional[datetime.date] = None
    filing_date: Optional[datetime.date] = None
    claimed_amount: Optional[float] = Field(None, gt=0.0)
    approved_amount: Optional[float] = Field(None, ge=0.0)
    status: Optional[ClaimStatus] = None
    fraud_risk_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    summary: Optional[str] = None
    fraud_indicators_summary: Optional[str] = None


class ClaimResponse(ClaimBase, TimestampedSchema):
    documents: List[ClaimDocumentResponse] = Field(default_factory=list)


class ClaimSummaryResponse(ClaimBase, TimestampedSchema):
    document_count: int = 0
    finding_count: int = 0
