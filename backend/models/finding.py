from typing import Optional
from sqlalchemy import String, Enum as SQLEnum, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.core.database import Base, TimestampMixin
from backend.models.enums import FindingType, FindingSeverity


class DiscrepancyFinding(Base, TimestampMixin):
    """Detailed audit finding indicating a potential fraud indicator, policy loophole, or inconsistency."""

    __tablename__ = "discrepancy_findings"

    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_type: Mapped[FindingType] = mapped_column(SQLEnum(FindingType), nullable=False, index=True)
    severity: Mapped[FindingSeverity] = mapped_column(
        SQLEnum(FindingSeverity), default=FindingSeverity.MEDIUM, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    suggested_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_verified_by_human: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    claim: Mapped["backend.models.claim.Claim"] = relationship("backend.models.claim.Claim", back_populates="findings")

    def __repr__(self) -> str:
        return f"<DiscrepancyFinding(id={self.id}, type='{self.finding_type}', severity='{self.severity}')>"
