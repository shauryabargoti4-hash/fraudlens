import datetime
import pytest
from sqlalchemy.orm import Session
from backend.models.policy import Policy
from backend.models.claim import Claim, ClaimDocument
from backend.models.document_chunk import DocumentChunk
from backend.models.enums import DocumentType, PolicyStatus, ClaimStatus
from backend.services.claim_retrieval_service import ClaimRetrievalService


def _seed_claim_and_policy(db: Session):
    policy = Policy(
        policy_number="POL-RETRIEVAL-001",
        title="Apex Corporate Health",
        insurer_name="Apex Mutual",
        policyholder_name="Alice Smith",
        effective_date=datetime.date(2026, 1, 1),
        expiration_date=datetime.date(2027, 1, 1),
        max_coverage_limit=250000.0,
        status=PolicyStatus.ACTIVE,
    )
    db.add(policy)
    db.commit()

    claim = Claim(
        claim_number="CLM-RETRIEVAL-001",
        policy_id=policy.id,
        claimant_name="Alice Smith",
        incident_date=datetime.date(2026, 3, 10),
        filing_date=datetime.date(2026, 3, 15),
        claimed_amount=4500.0,
        status=ClaimStatus.SUBMITTED,
    )
    db.add(claim)
    db.commit()

    # Policy chunks
    c_pol = DocumentChunk(
        policy_id=policy.id,
        chunk_index=0,
        clause_or_section_ref="SEC-1.1",
        page_number=1,
        text="Section 1.1 Inpatient hospital room is capped at $400/day.",
        metadata_json={"document_type": "policy_document"},
    )
    # Claim document & chunks
    doc = ClaimDocument(
        claim_id=claim.id,
        filename="hospital_bill.pdf",
        file_path="/storage/uploads/bill.pdf",
        file_hash="hash123",
        document_type=DocumentType.MEDICAL_INVOICE,
    )
    db.add(doc)
    db.commit()

    c_inv = DocumentChunk(
        claim_id=claim.id,
        claim_document_id=doc.id,
        chunk_index=0,
        clause_or_section_ref="Line 1",
        page_number=1,
        text="Hospital room charge: $1,200 for 3 nights.",
        metadata_json={"document_type": "medical_invoice"},
    )
    db.add_all([c_pol, c_inv])
    db.commit()

    return policy.id, claim.id


def test_claim_retrieval_service_success(db_session: Session):
    policy_id, claim_id = _seed_claim_and_policy(db_session)

    service = ClaimRetrievalService()
    pkg = service.retrieve_claim_evidence(db=db_session, claim_id=claim_id)

    assert pkg.claim_id == claim_id
    assert pkg.policy_id == policy_id
    assert pkg.claimant_name == "Alice Smith"
    assert pkg.claimed_amount == 4500.0
    assert len(pkg.policy_chunks) == 1
    assert len(pkg.invoice_chunks) == 1
    assert pkg.has_invoice is True
    assert pkg.has_policy_document is True


def test_claim_retrieval_service_nonexistent_claim(db_session: Session):
    service = ClaimRetrievalService()
    with pytest.raises(ValueError) as exc:
        service.retrieve_claim_evidence(db=db_session, claim_id=999999)
    assert "does not exist" in str(exc.value)


def test_claim_retrieval_service_cross_claim_isolation(db_session: Session):
    policy_id, claim_id_1 = _seed_claim_and_policy(db_session)

    # Create second unrelated claim under same policy
    claim2 = Claim(
        claim_number="CLM-RETRIEVAL-002",
        policy_id=policy_id,
        claimant_name="Bob Jones",
        incident_date=datetime.date(2026, 4, 1),
        filing_date=datetime.date(2026, 4, 5),
        claimed_amount=1500.0,
    )
    db_session.add(claim2)
    db_session.commit()

    c_claim2 = DocumentChunk(
        claim_id=claim2.id,
        chunk_index=0,
        text="Pharmacy charges for Bob: $300.",
        metadata_json={"document_type": "medical_invoice"},
    )
    db_session.add(c_claim2)
    db_session.commit()

    service = ClaimRetrievalService()
    # Retrieving claim 1 must not include claim 2 chunks
    pkg1 = service.retrieve_claim_evidence(db=db_session, claim_id=claim_id_1)
    for c in pkg1.all_chunks:
        assert c["claim_id"] != claim2.id
