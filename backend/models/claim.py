import datetime
from typing import List, Optional
from sqlalchemy import String, Date, Float, Enum as SQLEnum, Text, ForeignKey, JSON, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.core.database import Base, TimestampMixin
from backend.models.enums import ClaimStatus, DocumentType


class Claim(Base, TimestampMixin):
    """Insurance claim filed against an existing policy."""

    __tablename__ = "claims"

    claim_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True)
    claimant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    incident_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    filing_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    claimed_amount: Mapped[float] = mapped_column(Float, nullable=False)
    approved_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[ClaimStatus] = mapped_column(
        SQLEnum(ClaimStatus), default=ClaimStatus.SUBMITTED, nullable=False, index=True
    )
    fraud_risk_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 to 100.0
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fraud_indicators_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    policy: Mapped["backend.models.policy.Policy"] = relationship("backend.models.policy.Policy", back_populates="claims")
    documents: Mapped[List["ClaimDocument"]] = relationship(
        "ClaimDocument", back_populates="claim", cascade="all, delete-orphan"
    )
    findings: Mapped[List["backend.models.finding.DiscrepancyFinding"]] = relationship(
        "backend.models.finding.DiscrepancyFinding", back_populates="claim", cascade="all, delete-orphan"
    )
    reports: Mapped[List["backend.models.report.AnalysisReport"]] = relationship(
        "backend.models.report.AnalysisReport", back_populates="claim", cascade="all, delete-orphan"
    )
    document_chunks: Mapped[List["backend.models.document_chunk.DocumentChunk"]] = relationship(
        "backend.models.document_chunk.DocumentChunk", back_populates="claim", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Claim(id={self.id}, number='{self.claim_number}', status='{self.status}')>"


class ClaimDocument(Base, TimestampMixin):
    """Supporting documentation uploaded for a claim (bills, invoices, claim forms, etc.)."""

    __tablename__ = "claim_documents"

    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA256 checksum
    document_type: Mapped[DocumentType] = mapped_column(
        SQLEnum(DocumentType), default=DocumentType.OTHER, nullable=False
    )
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    ocr_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_metadata: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Relationships
    claim: Mapped["Claim"] = relationship("Claim", back_populates="documents")
    chunks: Mapped[List["backend.models.document_chunk.DocumentChunk"]] = relationship(
        "backend.models.document_chunk.DocumentChunk", back_populates="claim_document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ClaimDocument(id={self.id}, filename='{self.filename}', type='{self.document_type}')>"
