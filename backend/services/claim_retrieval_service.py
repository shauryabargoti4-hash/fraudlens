"""Claim-to-Policy Evidence Retrieval Service for ClauseGuard.

Retrieves policy clauses and claim evidence within strictly isolated
policy and claim boundaries to prevent cross-claim or cross-policy data contamination.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.core.logging_config import logger
from backend.crud.claim import get_claim
from backend.crud.policy import get_policy
from backend.crud.document_chunk import get_chunks_by_policy, get_chunks_by_claim
from backend.models.claim import Claim
from backend.models.policy import Policy
from backend.models.document_chunk import DocumentChunk
from backend.services.vector_store import VectorStore, get_vector_store


class ClaimEvidencePackage(BaseModel):
    """Categorized and validated evidence package for claim analysis."""

    claim_id: int
    policy_id: int
    claimant_name: str
    claimed_amount: float
    incident_date: str
    filing_date: str
    policy_number: str
    policy_effective_date: str = "2026-01-01"
    max_coverage_limit: float

    # Categorized chunk IDs and models
    policy_chunks: List[dict] = Field(default_factory=list)
    claim_form_chunks: List[dict] = Field(default_factory=list)
    invoice_chunks: List[dict] = Field(default_factory=list)
    supporting_evidence_chunks: List[dict] = Field(default_factory=list)
    all_chunks: List[dict] = Field(default_factory=list)

    total_evidence_count: int = 0
    has_invoice: bool = False
    has_claim_form: bool = False
    has_policy_document: bool = False


class ClaimRetrievalService:
    """Orchestrates structured retrieval of claim facts and policy contracts."""

    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store or get_vector_store()

    def retrieve_claim_evidence(
        self, db: Session, claim_id: int
    ) -> ClaimEvidencePackage:
        """Retrieves and partitions all policy rules and claim evidence for a given claim."""
        # 1. Fetch Target Claim
        claim: Optional[Claim] = get_claim(db, claim_id=claim_id)
        if not claim:
            raise ValueError(f"Target Claim with ID {claim_id} does not exist.")

        # 2. Fetch Associated Policy
        policy: Optional[Policy] = get_policy(db, policy_id=claim.policy_id)
        if not policy:
            raise ValueError(
                f"Parent Policy with ID {claim.policy_id} linked to Claim {claim_id} does not exist."
            )

        # 3. Retrieve Policy Chunks (authoritative from SQLite with policy_id isolation)
        db_policy_chunks = get_chunks_by_policy(db, policy_id=policy.id)

        # 4. Retrieve Claim Chunks (authoritative from SQLite with claim_id isolation)
        db_claim_chunks = get_chunks_by_claim(db, claim_id=claim.id)

        # 5. Partition Evidence into Categories
        policy_chunks_list = []
        claim_form_chunks = []
        invoice_chunks = []
        supporting_chunks = []
        all_chunks = []

        def _chunk_to_dict(c: DocumentChunk) -> dict:
            doc_type = "other"
            if c.metadata_json and isinstance(c.metadata_json, dict):
                doc_type = c.metadata_json.get("document_type", "other")
            return {
                "id": c.id,
                "chunk_index": c.chunk_index,
                "clause_or_section_ref": c.clause_or_section_ref,
                "page_number": c.page_number,
                "text": c.text,
                "document_type": doc_type,
                "policy_id": c.policy_id,
                "claim_id": c.claim_id,
                "claim_document_id": c.claim_document_id,
            }

        for c in db_policy_chunks:
            cd = _chunk_to_dict(c)
            cd["document_type"] = "policy_document"
            policy_chunks_list.append(cd)
            all_chunks.append(cd)

        for c in db_claim_chunks:
            cd = _chunk_to_dict(c)
            dtype = cd["document_type"]
            all_chunks.append(cd)
            if dtype in ["medical_invoice", "invoice", "repair_estimate"]:
                invoice_chunks.append(cd)
            elif dtype in ["claim_form"]:
                claim_form_chunks.append(cd)
            else:
                supporting_chunks.append(cd)

        logger.info(
            f"Evidence package retrieved for Claim {claim_id}: {len(policy_chunks_list)} policy clauses, "
            f"{len(invoice_chunks)} invoice items, {len(claim_form_chunks)} form items, "
            f"{len(supporting_chunks)} supporting items."
        )

        return ClaimEvidencePackage(
            claim_id=claim.id,
            policy_id=policy.id,
            claimant_name=claim.claimant_name,
            claimed_amount=claim.claimed_amount,
            incident_date=str(claim.incident_date),
            filing_date=str(claim.filing_date),
            policy_number=policy.policy_number,
            policy_effective_date=str(policy.effective_date),
            max_coverage_limit=policy.max_coverage_limit,
            policy_chunks=policy_chunks_list,
            claim_form_chunks=claim_form_chunks,
            invoice_chunks=invoice_chunks,
            supporting_evidence_chunks=supporting_chunks,
            all_chunks=all_chunks,
            total_evidence_count=len(all_chunks),
            has_invoice=len(invoice_chunks) > 0,
            has_claim_form=len(claim_form_chunks) > 0,
            has_policy_document=len(policy_chunks_list) > 0,
        )
