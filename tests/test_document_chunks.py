import datetime
from sqlalchemy.orm import Session
from backend.models.policy import Policy
from backend.models.claim import Claim, ClaimDocument
from backend.models.document_chunk import DocumentChunk
from backend.schemas.document_chunk import DocumentChunkCreate
from backend.crud.document_chunk import (
    create_chunk,
    create_chunks_batch,
    get_chunk,
    get_chunks_by_document,
    get_chunks_by_policy,
    get_chunks_by_claim,
    delete_chunk,
)


def _setup_entities(db_session: Session):
    policy = Policy(
        policy_number="POL-CHUNK-TEST",
        title="Health Shield Gold",
        insurer_name="Apex Assurance",
        policyholder_name="Alice Smith",
        effective_date=datetime.date(2026, 1, 1),
        expiration_date=datetime.date(2027, 1, 1),
        max_coverage_limit=250000.0,
    )
    db_session.add(policy)
    db_session.flush()

    claim = Claim(
        claim_number="CLM-CHUNK-TEST",
        policy_id=policy.id,
        claimant_name="Alice Smith",
        incident_date=datetime.date(2026, 3, 1),
        filing_date=datetime.date(2026, 3, 5),
        claimed_amount=4500.0,
    )
    db_session.add(claim)
    db_session.flush()

    doc = ClaimDocument(
        claim_id=claim.id,
        filename="hospital_receipt.pdf",
        file_path="/storage/uploads/receipt.pdf",
        file_hash="11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        page_count=2,
    )
    db_session.add(doc)
    db_session.commit()

    return policy, claim, doc


def test_create_and_retrieve_document_chunk(db_session: Session):
    policy, claim, doc = _setup_entities(db_session)

    chunk_in = DocumentChunkCreate(
        claim_document_id=doc.id,
        claim_id=claim.id,
        policy_id=policy.id,
        chunk_index=0,
        clause_or_section_ref="Section 1.1",
        page_number=1,
        text="Hospitalization bed charge: $600/day for 3 days.",
        metadata_json={"source": "test"},
    )
    chunk = create_chunk(db_session, chunk_in)

    assert chunk.id is not None
    assert chunk.chunk_index == 0
    assert chunk.clause_or_section_ref == "Section 1.1"
    assert chunk.text == "Hospitalization bed charge: $600/day for 3 days."
    assert chunk.claim_document_id == doc.id
    assert chunk.metadata_json["source"] == "test"

    # Retrieve by ID
    retrieved = get_chunk(db_session, chunk.id)
    assert retrieved is not None
    assert retrieved.id == chunk.id


def test_batch_create_and_ordering(db_session: Session):
    policy, claim, doc = _setup_entities(db_session)

    chunks_data = [
        DocumentChunkCreate(
            claim_document_id=doc.id,
            claim_id=claim.id,
            chunk_index=0,
            clause_or_section_ref="Part A",
            page_number=1,
            text="First chunk text.",
        ),
        DocumentChunkCreate(
            claim_document_id=doc.id,
            claim_id=claim.id,
            chunk_index=1,
            clause_or_section_ref="Part B",
            page_number=1,
            text="Second chunk text.",
        ),
        DocumentChunkCreate(
            claim_document_id=doc.id,
            claim_id=claim.id,
            chunk_index=2,
            clause_or_section_ref="Part C",
            page_number=2,
            text="Third chunk text on page 2.",
        ),
    ]

    saved = create_chunks_batch(db_session, chunks_data)
    assert len(saved) == 3

    # Query by document
    doc_chunks = get_chunks_by_document(db_session, claim_document_id=doc.id)
    assert len(doc_chunks) == 3
    assert [c.chunk_index for c in doc_chunks] == [0, 1, 2]

    # Query by claim
    claim_chunks = get_chunks_by_claim(db_session, claim_id=claim.id)
    assert len(claim_chunks) == 3


def test_policy_chunks_association_and_cascade(db_session: Session):
    policy, _, _ = _setup_entities(db_session)

    chunk_in = DocumentChunkCreate(
        policy_id=policy.id,
        chunk_index=0,
        clause_or_section_ref="Clause 4.1",
        page_number=1,
        text="Exclusion: Cosmetic rhinoplasty is strictly non-reimbursable.",
    )
    chunk = create_chunk(db_session, chunk_in)
    chunk_id = chunk.id

    policy_chunks = get_chunks_by_policy(db_session, policy_id=policy.id)
    assert len(policy_chunks) == 1
    assert policy_chunks[0].clause_or_section_ref == "Clause 4.1"

    # Delete policy -> verify chunk cascades
    db_session.delete(policy)
    db_session.commit()

    assert get_chunk(db_session, chunk_id) is None


def test_delete_chunk_direct(db_session: Session):
    policy, _, doc = _setup_entities(db_session)
    chunk = create_chunk(
        db_session,
        DocumentChunkCreate(
            claim_document_id=doc.id,
            chunk_index=0,
            page_number=1,
            text="Temporary chunk",
        ),
    )
    chunk_id = chunk.id
    assert delete_chunk(db_session, chunk_id) is True
    assert get_chunk(db_session, chunk_id) is None
    assert delete_chunk(db_session, chunk_id) is False
