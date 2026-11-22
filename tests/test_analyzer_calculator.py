from backend.models.enums import ClauseType, FindingType, FindingSeverity, ReviewerOutcome
from backend.services.claim_retrieval_service import ClaimEvidencePackage
from backend.services.policy_rule_extractor import ExtractedPolicyRule
from backend.services.clause_reviewer import ReviewerSummary, ClauseReviewAssessment
from backend.services.analyzer_calculator import AnalyzerCalculator


def test_analyzer_detects_date_inconsistency():
    # Invoice dated 2026-02-15 but declared incident date is 2026-02-20 (Invoice precedes incident!)
    evidence = ClaimEvidencePackage(
        claim_id=1,
        policy_id=10,
        claimant_name="David Vance",
        claimed_amount=3000.0,
        incident_date="2026-02-20",
        filing_date="2026-02-25",
        policy_number="POL-100",
        max_coverage_limit=100000.0,
        invoice_chunks=[{"text": "Invoice Date: 2026-02-15. Hospital admission charges: $3,000.", "document_type": "medical_invoice", "id": 1}],
        claim_form_chunks=[{"text": "Accident occurred on 2026-02-20.", "document_type": "claim_form", "id": 2}],
        policy_chunks=[],
        all_chunks=[],
        total_evidence_count=2,
        has_invoice=True,
        has_claim_form=True,
        has_policy_document=True,
    )
    reviewer_summary = ReviewerSummary(total_reviewed=0)
    analyzer = AnalyzerCalculator()
    res = analyzer.analyze_and_calculate(evidence=evidence, reviewer_summary=reviewer_summary, rules=[])

    assert res.material_contradictions_found is True
    assert any(f.finding_type == FindingType.DATE_MISMATCH for f in res.fraud_signals)


def test_analyzer_detects_missing_mandatory_invoice():
    evidence = ClaimEvidencePackage(
        claim_id=2,
        policy_id=10,
        claimant_name="Alice Brown",
        claimed_amount=2000.0,
        incident_date="2026-03-01",
        filing_date="2026-03-05",
        policy_number="POL-100",
        max_coverage_limit=100000.0,
        invoice_chunks=[],  # No invoices!
        claim_form_chunks=[{"text": "Signed claim form", "document_type": "claim_form", "id": 2}],
        policy_chunks=[],
        all_chunks=[],
        total_evidence_count=1,
        has_invoice=False,
        has_claim_form=True,
        has_policy_document=True,
    )
    reviewer_summary = ReviewerSummary(total_reviewed=0)
    analyzer = AnalyzerCalculator()
    res = analyzer.analyze_and_calculate(evidence=evidence, reviewer_summary=reviewer_summary, rules=[])

    assert "Original Itemized Hospital Invoice" in res.missing_documents
    assert any(f.finding_type == FindingType.MISSING_DOCUMENT for f in res.fraud_signals)


def test_calculator_applies_room_sub_limit_and_deductible():
    # 4 nights room billed at $600 = $2,400. Approved sub-limit is $500/day ($2,000 cap). Excess = $400.
    # Deductible is $250.
    evidence = ClaimEvidencePackage(
        claim_id=3,
        policy_id=10,
        claimant_name="Carol White",
        claimed_amount=2400.0,
        incident_date="2026-03-01",
        filing_date="2026-03-05",
        policy_number="POL-100",
        max_coverage_limit=100000.0,
        invoice_chunks=[{"text": "Hospital Room Charges: 4 nights @ $600/night = $2,400.", "document_type": "medical_invoice", "id": 1}],
        claim_form_chunks=[{"text": "Claim form", "document_type": "claim_form", "id": 2}],
        policy_chunks=[],
        all_chunks=[],
        total_evidence_count=2,
        has_invoice=True,
        has_claim_form=True,
        has_policy_document=True,
    )

    rule_sub = ExtractedPolicyRule(
        rule_id="RULE-ROOM",
        rule_type=ClauseType.SUB_LIMIT,
        rule_description="Room sub-limit $500/day",
        limit_amount=500.0,
        clause_reference="SEC-2.1",
        page_number=1,
        source_chunk_id=1,
        source_text_excerpt="Room sub-limit $500/day",
    )
    rule_ded = ExtractedPolicyRule(
        rule_id="RULE-DED",
        rule_type=ClauseType.DEDUCTIBLE,
        rule_description="Annual deductible $250",
        deductible_amount=250.0,
        clause_reference="SEC-1.2",
        page_number=1,
        source_chunk_id=2,
        source_text_excerpt="Deductible $250",
    )

    approved = [
        ClauseReviewAssessment(
            rule_id="RULE-ROOM",
            clause_reference="SEC-2.1",
            page_number=1,
            source_chunk_id=1,
            source_text="Room sub-limit $500/day",
            outcome=ReviewerOutcome.APPROVED,
            applicability_reason="Invoice contains room rent",
        ),
        ClauseReviewAssessment(
            rule_id="RULE-DED",
            clause_reference="SEC-1.2",
            page_number=1,
            source_chunk_id=2,
            source_text="Deductible $250",
            outcome=ReviewerOutcome.APPROVED,
            applicability_reason="General policy deductible",
        ),
    ]

    reviewer_summary = ReviewerSummary(
        total_reviewed=2,
        approved_rules=approved,
    )

    analyzer = AnalyzerCalculator()
    res = analyzer.analyze_and_calculate(
        evidence=evidence,
        reviewer_summary=reviewer_summary,
        rules=[rule_sub, rule_ded],
    )

    calcs = res.calculations
    assert calcs.total_billed_amount == 2400.0
    assert calcs.room_excess_deduction == 400.0  # 2400 - 2000
    assert calcs.deductible_applied == 250.0
    assert calcs.total_non_eligible_amount == 650.0  # 400 + 250
    assert calcs.net_eligible_amount == 1750.0  # 2400 - 650
