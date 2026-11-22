from backend.models.enums import ClauseType, ReviewerOutcome
from backend.services.claim_retrieval_service import ClaimEvidencePackage
from backend.services.policy_rule_extractor import ExtractedPolicyRule
from backend.services.clause_reviewer import ClauseReviewer


def _build_sample_evidence(has_room: bool = True, has_cosmetic: bool = False) -> ClaimEvidencePackage:
    invoice_text = "Hospital stay details:\n"
    if has_room:
        invoice_text += "Line 1. Private Room Charge: 3 nights @ $600 = $1,800.\n"
    if has_cosmetic:
        invoice_text += "Line 2. Elective Rhinoplasty Aesthetic Surgery: $3,500.\n"
    invoice_text += "Line 3. Pharmacy items: $250.\n"

    return ClaimEvidencePackage(
        claim_id=1,
        policy_id=10,
        claimant_name="Jane Doe",
        claimed_amount=5550.0,
        incident_date="2026-03-01",
        filing_date="2026-03-05",
        policy_number="POL-100",
        max_coverage_limit=100000.0,
        invoice_chunks=[{"text": invoice_text, "document_type": "medical_invoice", "id": 10}],
        claim_form_chunks=[{"text": "Claim for acute appendicitis admission.", "document_type": "claim_form", "id": 11}],
        policy_chunks=[],
        all_chunks=[],
        total_evidence_count=2,
        has_invoice=True,
        has_claim_form=True,
        has_policy_document=True,
    )


def test_reviewer_approves_applicable_room_sub_limit():
    evidence = _build_sample_evidence(has_room=True)
    rule = ExtractedPolicyRule(
        rule_id="RULE-ROOM-01",
        rule_type=ClauseType.SUB_LIMIT,
        rule_description="Inpatient room and board sub-limit capped at $500/day",
        limit_amount=500.0,
        clause_reference="SEC-2.1",
        page_number=1,
        source_chunk_id=1,
        source_text_excerpt="Room sub-limit $500/day",
    )
    reviewer = ClauseReviewer()
    summary = reviewer.review_rules(rules=[rule], evidence=evidence)

    assert len(summary.approved_rules) == 1
    assert summary.approved_rules[0].outcome == ReviewerOutcome.APPROVED
    assert "room" in summary.approved_rules[0].applicability_reason.lower()


def test_reviewer_rejects_sub_limit_not_in_invoice_prevents_contamination():
    # Invoice has no room charges
    evidence = _build_sample_evidence(has_room=False)
    rule = ExtractedPolicyRule(
        rule_id="RULE-ROOM-01",
        rule_type=ClauseType.SUB_LIMIT,
        rule_description="Inpatient room and board sub-limit capped at $500/day",
        limit_amount=500.0,
        clause_reference="SEC-2.1",
        page_number=1,
        source_chunk_id=1,
        source_text_excerpt="Room sub-limit $500/day",
    )
    reviewer = ClauseReviewer()
    summary = reviewer.review_rules(rules=[rule], evidence=evidence)

    # Must be REJECTED to prevent cross-clause contamination into pharmacy lines
    assert len(summary.rejected_rules) == 1
    assert summary.rejected_rules[0].outcome == ReviewerOutcome.REJECTED


def test_reviewer_approves_cosmetic_exclusion_when_present():
    evidence = _build_sample_evidence(has_cosmetic=True)
    rule = ExtractedPolicyRule(
        rule_id="RULE-EXCL-01",
        rule_type=ClauseType.EXCLUSION,
        rule_description="Exclusion of cosmetic and aesthetic procedures",
        clause_reference="SEC-4.1",
        page_number=2,
        source_chunk_id=2,
        source_text_excerpt="Cosmetic procedures strictly excluded",
    )
    reviewer = ClauseReviewer()
    summary = reviewer.review_rules(rules=[rule], evidence=evidence)

    assert len(summary.approved_rules) == 1
    assert summary.approved_rules[0].outcome == ReviewerOutcome.APPROVED


def test_reviewer_flags_ambiguous_clause_as_uncertain():
    evidence = _build_sample_evidence()
    rule = ExtractedPolicyRule(
        rule_id="RULE-AMBIG-01",
        rule_type=ClauseType.COVERAGE_SCOPE,
        rule_description="Reimbursement of reasonable and customary hospital charges",
        clause_reference="SEC-1.5",
        page_number=1,
        source_chunk_id=3,
        source_text_excerpt="Charges must be reasonable and customary",
        ambiguity_flag=True,
    )
    reviewer = ClauseReviewer()
    summary = reviewer.review_rules(rules=[rule], evidence=evidence)

    assert len(summary.uncertain_rules) == 1
    assert summary.uncertain_rules[0].outcome == ReviewerOutcome.UNCERTAIN
    assert summary.uncertain_rules[0].is_ambiguous is True
