import datetime
from sqlalchemy.orm import Session
from backend.models.enums import (
    PolicyStatus,
    ClauseType,
    ClaimStatus,
    DocumentType,
    FindingType,
    FindingSeverity,
    RecommendationType,
)
from backend.models.policy import Policy, PolicyClause
from backend.models.claim import Claim, ClaimDocument
from backend.models.finding import DiscrepancyFinding
from backend.models.report import AnalysisReport, AuditLog


def test_create_policy_and_clauses(db_session: Session):
    policy = Policy(
        policy_number="POL-2026-TEST-001",
        title="Comprehensive Health Shield",
        insurer_name="Apex Mutual Assurance",
        policyholder_name="Jane Doe",
        effective_date=datetime.date(2026, 1, 1),
        expiration_date=datetime.date(2027, 1, 1),
        premium_amount=1200.0,
        max_coverage_limit=500000.0,
        status=PolicyStatus.ACTIVE,
    )
    db_session.add(policy)
    db_session.commit()
    db_session.refresh(policy)

    assert policy.id is not None
    assert policy.policy_number == "POL-2026-TEST-001"
    assert policy.status == PolicyStatus.ACTIVE

    # Add a clause
    clause = PolicyClause(
        policy_id=policy.id,
        clause_code="EXCL-01",
        clause_type=ClauseType.EXCLUSION,
        title="Cosmetic Surgery Exclusion",
        clause_text="Cosmetic and elective aesthetic procedures are strictly excluded.",
        ambiguity_score=15.0,
    )
    db_session.add(clause)
    db_session.commit()
    db_session.refresh(policy)

    assert len(policy.clauses) == 1
    assert policy.clauses[0].clause_code == "EXCL-01"


def test_claim_with_documents_and_findings(db_session: Session):
    policy = Policy(
        policy_number="POL-CLAIM-TEST",
        title="Standard Health Plan",
        insurer_name="Apex Mutual",
        policyholder_name="John Smith",
        effective_date=datetime.date(2026, 1, 1),
        expiration_date=datetime.date(2027, 1, 1),
        max_coverage_limit=100000.0,
    )
    db_session.add(policy)
    db_session.commit()

    claim = Claim(
        claim_number="CLM-2026-0001",
        policy_id=policy.id,
        claimant_name="John Smith",
        incident_date=datetime.date(2026, 3, 1),
        filing_date=datetime.date(2026, 3, 5),
        claimed_amount=8500.0,
        status=ClaimStatus.UNDER_REVIEW,
        fraud_risk_score=65.5,
    )
    db_session.add(claim)
    db_session.commit()
    db_session.refresh(claim)

    assert claim.id is not None

    # Attach document
    doc = ClaimDocument(
        claim_id=claim.id,
        filename="hospital_invoice.pdf",
        file_path="/storage/uploads/hospital_invoice.pdf",
        file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        document_type=DocumentType.MEDICAL_INVOICE,
    )
    db_session.add(doc)

    # Attach finding
    finding = DiscrepancyFinding(
        claim_id=claim.id,
        finding_type=FindingType.DATE_MISMATCH,
        severity=FindingSeverity.HIGH,
        title="Invoice date precedes incident date",
        description="The medical invoice date is dated 2026-02-28, which precedes the claimed incident date 2026-03-01.",
    )
    db_session.add(finding)

    # Attach report
    report = AnalysisReport(
        claim_id=claim.id,
        overall_risk_score=75.0,
        recommendation=RecommendationType.MANUAL_INVESTIGATION,
        confidence_score=0.92,
        executive_summary="Claim exhibits critical date discrepancy between admission invoice and declared accident date.",
        findings_count=1,
    )
    db_session.add(report)

    db_session.commit()
    db_session.refresh(claim)

    assert len(claim.documents) == 1
    assert len(claim.findings) == 1
    assert len(claim.reports) == 1
    assert claim.findings[0].severity == FindingSeverity.HIGH


def test_cascade_deletion(db_session: Session):
    policy = Policy(
        policy_number="POL-CASCADE",
        title="Auto Shield",
        insurer_name="Apex Mutual",
        policyholder_name="Alice Blue",
        effective_date=datetime.date(2026, 1, 1),
        expiration_date=datetime.date(2027, 1, 1),
        max_coverage_limit=50000.0,
    )
    db_session.add(policy)
    db_session.commit()

    clause = PolicyClause(
        policy_id=policy.id,
        clause_code="SUB-01",
        clause_type=ClauseType.SUB_LIMIT,
        title="Windshield Limit",
        clause_text="Windshield damage is capped at 500.",
        limit_amount=500.0,
    )
    db_session.add(clause)
    db_session.commit()

    clause_id = clause.id
    # Delete policy
    db_session.delete(policy)
    db_session.commit()

    # Clause should be deleted due to cascade
    deleted_clause = db_session.get(PolicyClause, clause_id)
    assert deleted_clause is None
