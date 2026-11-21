import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, ForeignKey, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.core.database import Base


class DocumentChunk(Base):
    """Segmented text chunk extracted from a policy or claim document, retaining page and clause provenance."""

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    claim_document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("claim_documents.id", ondelete="CASCADE"), nullable=True, index=True
    )
    policy_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), nullable=True, index=True
    )
    claim_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=True, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    clause_or_section_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False
    )

    # Relationships
    claim_document: Mapped[Optional["backend.models.claim.ClaimDocument"]] = relationship(
        "backend.models.claim.ClaimDocument", back_populates="chunks"
    )
    policy: Mapped[Optional["backend.models.policy.Policy"]] = relationship(
        "backend.models.policy.Policy", back_populates="document_chunks"
    )
    claim: Mapped[Optional["backend.models.claim.Claim"]] = relationship(
        "backend.models.claim.Claim", back_populates="document_chunks"
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk(id={self.id}, index={self.chunk_index}, "
            f"page={self.page_number}, ref='{self.clause_or_section_ref}')>"
        )
