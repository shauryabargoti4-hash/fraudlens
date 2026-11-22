import datetime
from sqlalchemy.orm import Session
from backend.models.policy import Policy
from backend.models.claim import Claim, ClaimDocument
from backend.models.document_chunk import DocumentChunk
from backend.models.enums import DocumentType, PolicyStatus, ClaimStatus, AdvisoryVerdict
from backend.models.report import AnalysisReport, AuditLog
from backend.models.finding import DiscrepancyFinding
from backend.services.llm_provider import MockLLMProvider
from backend.workflows.claim_analysis_workflow import run_claim_analysis, claim_analysis_graph


def _seed_test_claim(db: Session) -> tuple[int, int]:
    policy = Policy(
        policy_number="POL-WORKFLOW-TEST",
        title="Comprehensive Health Shield",
        insurer_name="Apex Assurance",
        policyholder_name="Jane Doe",
        effective_date=datetime.date(2026, 1, 1),
        expiration_date=datetime.date(2027, 1, 1),
        max_coverage_limit=500000.0,
        status=PolicyStatus.ACTIVE,
    )
    db.add(policy)
    db.commit()

    claim = Claim(
        claim_number="CLM-WORKFLOW-TEST",
        policy_id=policy.id,
        claimant_name="Jane Doe",
        incident_date=datetime.date(2026, 3, 1),
        filing_date=datetime.date(2026, 3, 5),
        claimed_amount=3200.0,
        status=ClaimStatus.SUBMITTED,
    )
    db.add(claim)
    db.commit()

    # Policy chunks: sub-limit $500/day
    c_pol = DocumentChunk(
        policy_id=policy.id,
        chunk_index=0,
        clause_or_section_ref="SEC-2.1",
        page_number=1,
        text="Section 2.1: Inpatient room and board is subject to a daily sub-limit capped at $500 per day.",
        metadata_json={"document_type": "policy_document"},
    )
    db.add(c_pol)

    # Claim doc & invoice chunk
    doc = ClaimDocument(
        claim_id=claim.id,
        filename="invoice.pdf",
        file_path="/storage/uploads/inv.pdf",
        file_hash="hash_inv",
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
        text="Hospital Room Charge: 4 nights @ $500/night = $2,000. Pharmacy charges: $1,200. Total = $3,200.",
        metadata_json={"document_type": "medical_invoice"},
    )
    # Claim form doc
    doc_form = ClaimDocument(
        claim_id=claim.id,
        filename="form.pdf",
        file_path="/storage/uploads/form.pdf",
        file_hash="hash_form",
        document_type=DocumentType.CLAIM_FORM,
    )
    db.add(doc_form)
    db.commit()

    c_form = DocumentChunk(
        claim_id=claim.id,
        claim_document_id=doc_form.id,
        chunk_index=0,
        clause_or_section_ref="Section A",
        page_number=1,
        text="Claim declaration form signed by Jane Doe.",
        metadata_json={"document_type": "claim_form"},
    )
    db.add_all([c_inv, c_form])
    db.commit()

    return policy.id, claim.id


def test_full_langgraph_workflow_execution(db_session: Session):
    policy_id, claim_id = _seed_test_claim(db_session)
    mock_llm = MockLLMProvider()

    report = run_claim_analysis(
        claim_id=claim_id,
        db=db_session,
        llm_provider=mock_llm,
    )

    # Verify Report Content
    assert report.claim_id == claim_id
    assert report.policy_id == policy_id
    assert report.claimant_name == "Jane Doe"
    assert report.verdict == AdvisoryVerdict.TAKE
    assert report.calculations.claimed_amount == 3200.0
    assert report.calculations.net_eligible_amount > 0.0

    # Verify SQLite Persistence
    db_reports = db_session.query(AnalysisReport).filter(AnalysisReport.claim_id == claim_id).all()
    assert len(db_reports) >= 1
    assert db_reports[0].id == report.report_id
    assert db_reports[0].executive_summary is not None
    assert db_reports[0].agent_trace is not None
    assert "verdict" in db_reports[0].agent_trace

    # Verify AuditLog Record
    audit_logs = db_session.query(AuditLog).filter(AuditLog.entity_id == str(claim_id)).all()
    assert len(audit_logs) >= 1
    assert any(a.action == "analysis_completed" for a in audit_logs)
