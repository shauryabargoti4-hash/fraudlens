import datetime
from typing import List, Optional
from pydantic import Field, field_validator, model_validator
from backend.models.enums import PolicyStatus, ClauseType
from backend.schemas.common import BaseSchema, TimestampedSchema


class PolicyClauseBase(BaseSchema):
    clause_code: str = Field(..., min_length=1, max_length=100, description="Clause code identifier, e.g., SEC-4.1")
    clause_type: ClauseType
    title: str = Field(..., min_length=2, max_length=255)
    clause_text: str = Field(..., min_length=5, description="Full extracted or specified clause text")
    limit_amount: Optional[float] = Field(None, ge=0.0)
    waiting_period_days: Optional[int] = Field(None, ge=0)
    deductible_amount: Optional[float] = Field(None, ge=0.0)
    applicable_categories: Optional[str] = None
    ambiguity_score: float = Field(0.0, ge=0.0, le=100.0)
    ambiguity_notes: Optional[str] = None


class PolicyClauseCreate(PolicyClauseBase):
    pass


class PolicyClauseResponse(PolicyClauseBase, TimestampedSchema):
    policy_id: int


class PolicyBase(BaseSchema):
    policy_number: str = Field(..., min_length=3, max_length=100)
    title: str = Field(..., min_length=3, max_length=255)
    insurer_name: str = Field(..., min_length=2, max_length=255)
    policyholder_name: str = Field(..., min_length=2, max_length=255)
    policy_type: str = Field("health", max_length=100)
    effective_date: datetime.date
    expiration_date: datetime.date
    premium_amount: float = Field(0.0, ge=0.0)
    max_coverage_limit: float = Field(..., gt=0.0)
    status: PolicyStatus = PolicyStatus.ACTIVE
    metadata_json: Optional[dict] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dates(self) -> "PolicyBase":
        if self.expiration_date < self.effective_date:
            raise ValueError("expiration_date cannot be earlier than effective_date")
        return self


class PolicyCreate(PolicyBase):
    document_path: Optional[str] = None
    raw_text: Optional[str] = None
    clauses: Optional[List[PolicyClauseCreate]] = Field(default_factory=list)


class PolicyUpdate(BaseSchema):
    title: Optional[str] = None
    insurer_name: Optional[str] = None
    policyholder_name: Optional[str] = None
    effective_date: Optional[datetime.date] = None
    expiration_date: Optional[datetime.date] = None
    premium_amount: Optional[float] = Field(None, ge=0.0)
    max_coverage_limit: Optional[float] = Field(None, gt=0.0)
    status: Optional[PolicyStatus] = None
    metadata_json: Optional[dict] = None


class PolicyResponse(PolicyBase, TimestampedSchema):
    document_path: Optional[str] = None
    raw_text: Optional[str] = None
    clauses: List[PolicyClauseResponse] = Field(default_factory=list)


class PolicySummaryResponse(PolicyBase, TimestampedSchema):
    clause_count: int = 0
    claim_count: int = 0
