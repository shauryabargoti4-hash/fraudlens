import datetime
from typing import List, Optional
from sqlalchemy import String, Date, Float, Enum as SQLEnum, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.core.database import Base, TimestampMixin
from backend.models.enums import PolicyStatus, ClauseType


class Policy(Base, TimestampMixin):
    """Insurance policy model representing the master policy contract and its metadata."""

    __tablename__ = "policies"

    policy_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    insurer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    policyholder_name: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_type: Mapped[str] = mapped_column(String(100), default="health")  # health, motor, property, life
    effective_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    premium_amount: Mapped[float] = mapped_column(Float, default=0.0)
    max_coverage_limit: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[PolicyStatus] = mapped_column(
        SQLEnum(PolicyStatus), default=PolicyStatus.ACTIVE, nullable=False
    )
    document_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Relationships
    clauses: Mapped[List["PolicyClause"]] = relationship(
        "PolicyClause", back_populates="policy", cascade="all, delete-orphan"
    )
    claims: Mapped[List["Claim"]] = relationship(
        "backend.models.claim.Claim", back_populates="policy", cascade="all, delete-orphan"
    )
    document_chunks: Mapped[List["backend.models.document_chunk.DocumentChunk"]] = relationship(
        "backend.models.document_chunk.DocumentChunk", back_populates="policy", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Policy(id={self.id}, number='{self.policy_number}', title='{self.title}')>"


class PolicyClause(Base, TimestampMixin):
    """Structured clause extracted from a policy (e.g. exclusions, sub-limits, waiting periods)."""

    __tablename__ = "policy_clauses"

    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True)
    clause_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # e.g., "SEC-4.2", "EXCL-01"
    clause_type: Mapped[ClauseType] = mapped_column(SQLEnum(ClauseType), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    clause_text: Mapped[str] = mapped_column(Text, nullable=False)
    limit_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    waiting_period_days: Mapped[Optional[int]] = mapped_column(nullable=True)
    deductible_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    applicable_categories: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ambiguity_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 (crystal clear) to 100.0 (high loophole risk)
    ambiguity_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    policy: Mapped["Policy"] = relationship("Policy", back_populates="clauses")

    def __repr__(self) -> str:
        return f"<PolicyClause(id={self.id}, code='{self.clause_code}', type='{self.clause_type}')>"
