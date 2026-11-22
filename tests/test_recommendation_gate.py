from backend.models.enums import AdvisoryVerdict, ReviewerOutcome
from backend.services.analyzer_calculator import AnalysisCalculationResult, CalculationSummary, DiscrepancyItem
from backend.services.clause_reviewer import ReviewerSummary, ClauseReviewAssessment
from backend.services.recommendation_gate import DeterministicRecommendationGate


def _base_calc_summary(
    claimed: float = 3000.0,
    net: float = 3000.0,
    is_excl: bool = False,
    is_wait: bool = False,
) -> CalculationSummary:
    return CalculationSummary(
        claimed_amount=claimed,
        total_billed_amount=claimed,
        net_eligible_amount=net,
        is_exclusion_violated=is_excl,
        is_waiting_period_violated=is_wait,
        exclusion_deduction=1500.0 if is_excl else 0.0,
        waiting_period_days_required=30 if is_wait else 0,
        days_since_policy_inception=15 if is_wait else 60,
    )


def test_gate_verdict_take_when_clean_and_supported():
    analysis_res = AnalysisCalculationResult(
        fraud_signals=[],
        policy_loopholes=[],
        calculations=_base_calc_summary(),
        missing_documents=[],
        material_contradictions_found=False,
    )
    reviewer_summary = ReviewerSummary(
        total_reviewed=1,
        approved_rules=[
            ClauseReviewAssessment(
                rule_id="RULE-1",
                clause_reference="SEC-1",
                page_number=1,
                source_chunk_id=1,
                source_text="Coverage",
                outcome=ReviewerOutcome.APPROVED,
                applicability_reason="Verified",
            )
        ],
    )
    gate = DeterministicRecommendationGate()
    verdict = gate.evaluate(analysis_result=analysis_res, reviewer_summary=reviewer_summary)

    assert verdict.verdict == AdvisoryVerdict.TAKE
    assert verdict.human_review_required is False
    assert len(verdict.top_reasons) >= 1
    assert "None" in verdict.conditions_to_change_verdict[0]


def test_gate_verdict_review_required_on_missing_documents():
    analysis_res = AnalysisCalculationResult(
        fraud_signals=[],
        policy_loopholes=[],
        calculations=_base_calc_summary(),
        missing_documents=["Original Itemized Hospital Invoice"],
        material_contradictions_found=False,
    )
    reviewer_summary = ReviewerSummary(total_reviewed=1)
    gate = DeterministicRecommendationGate()
    verdict = gate.evaluate(analysis_result=analysis_res, reviewer_summary=reviewer_summary)

    assert verdict.verdict == AdvisoryVerdict.REVIEW_REQUIRED
    assert verdict.human_review_required is True
    assert "Original Itemized Hospital Invoice" in verdict.missing_documents
    assert any("missing" in r.lower() for r in verdict.top_reasons)


def test_gate_verdict_review_required_on_material_contradiction():
    analysis_res = AnalysisCalculationResult(
        fraud_signals=[],
        policy_loopholes=[],
        calculations=_base_calc_summary(),
        missing_documents=[],
        material_contradictions_found=True,
    )
    reviewer_summary = ReviewerSummary(total_reviewed=1)
    gate = DeterministicRecommendationGate()
    verdict = gate.evaluate(analysis_result=analysis_res, reviewer_summary=reviewer_summary)

    assert verdict.verdict == AdvisoryVerdict.REVIEW_REQUIRED
    assert verdict.human_review_required is True
    assert any("mismatch" in r.lower() or "date" in r.lower() for r in verdict.top_reasons)


def test_gate_verdict_do_not_take_on_verified_exclusion():
    analysis_res = AnalysisCalculationResult(
        fraud_signals=[],
        policy_loopholes=[],
        calculations=_base_calc_summary(is_excl=True),
        missing_documents=[],
        material_contradictions_found=False,
    )
    reviewer_summary = ReviewerSummary(
        total_reviewed=1,
        approved_rules=[
            ClauseReviewAssessment(
                rule_id="RULE-EXCL",
                clause_reference="SEC-4.1",
                page_number=2,
                source_chunk_id=2,
                source_text="Exclusion",
                outcome=ReviewerOutcome.APPROVED,
                applicability_reason="Cosmetic exclusion applies",
            )
        ],
    )
    gate = DeterministicRecommendationGate()
    verdict = gate.evaluate(analysis_result=analysis_res, reviewer_summary=reviewer_summary)

    assert verdict.verdict == AdvisoryVerdict.DO_NOT_TAKE
    assert verdict.human_review_required is True
    assert any("excluded" in r.lower() for r in verdict.top_reasons)


def test_gate_verdict_do_not_take_on_verified_waiting_period_breach():
    analysis_res = AnalysisCalculationResult(
        fraud_signals=[],
        policy_loopholes=[],
        calculations=_base_calc_summary(is_wait=True),
        missing_documents=[],
        material_contradictions_found=False,
    )
    reviewer_summary = ReviewerSummary(total_reviewed=1)
    gate = DeterministicRecommendationGate()
    verdict = gate.evaluate(analysis_result=analysis_res, reviewer_summary=reviewer_summary)

    assert verdict.verdict == AdvisoryVerdict.DO_NOT_TAKE
    assert any("waiting period" in r.lower() for r in verdict.top_reasons)


def test_gate_ambiguous_exclusion_escalates_to_review_required_not_do_not_take():
    # When clause is UNCERTAIN (ambiguous wording), it must NEVER trigger DO_NOT_TAKE!
    analysis_res = AnalysisCalculationResult(
        fraud_signals=[],
        policy_loopholes=[],
        calculations=_base_calc_summary(is_excl=False),  # Not confirmed
        missing_documents=[],
        material_contradictions_found=False,
    )
    reviewer_summary = ReviewerSummary(
        total_reviewed=1,
        uncertain_rules=[
            ClauseReviewAssessment(
                rule_id="RULE-AMBIG",
                clause_reference="SEC-AMBIG",
                page_number=1,
                source_chunk_id=1,
                source_text="Vague exclusion",
                outcome=ReviewerOutcome.UNCERTAIN,
                applicability_reason="Ambiguous terminology",
                is_ambiguous=True,
            )
        ],
    )
    gate = DeterministicRecommendationGate()
    verdict = gate.evaluate(analysis_result=analysis_res, reviewer_summary=reviewer_summary)

    # Must escalate to REVIEW_REQUIRED, not DO_NOT_TAKE
    assert verdict.verdict == AdvisoryVerdict.REVIEW_REQUIRED
    assert verdict.verdict != AdvisoryVerdict.DO_NOT_TAKE
