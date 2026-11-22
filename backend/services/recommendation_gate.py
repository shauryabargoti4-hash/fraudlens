"""Deterministic Recommendation Gate for ClauseGuard.

Advisory "Should We Take This?" decision-support engine.
Applies deterministic priority rules to structured findings and calculation outcomes.
NEVER relies on LLM heuristics or uncalibrated probabilities to decide verdicts.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from backend.core.logging_config import logger
from backend.models.enums import AdvisoryVerdict, FindingSeverity
from backend.services.analyzer_calculator import AnalysisCalculationResult
from backend.services.clause_reviewer import ReviewerSummary


class RecommendationVerdict(BaseModel):
    """Structured, evidence-grounded advisory review outcome."""

    verdict: AdvisoryVerdict
    risk_score: Optional[float] = Field(None, description="Deterministic risk score (0.0 to 100.0) or None")
    risk_score_components: Dict[str, float] = Field(default_factory=dict)
    top_reasons: List[str] = Field(default_factory=list)
    conditions_to_change_verdict: List[str] = Field(default_factory=list)
    missing_documents: List[str] = Field(default_factory=list)
    unresolved_issues: List[str] = Field(default_factory=list)
    approved_clause_refs: List[str] = Field(default_factory=list)
    rejected_clause_refs: List[str] = Field(default_factory=list)
    uncertain_clause_refs: List[str] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    human_review_required: bool = True


class DeterministicRecommendationGate:
    """Evaluates objective conditions in fixed hierarchical order."""

    def evaluate(
        self,
        analysis_result: AnalysisCalculationResult,
        reviewer_summary: ReviewerSummary,
        fallback_used: bool = False,
        fallback_reason: Optional[str] = None,
    ) -> RecommendationVerdict:
        """Determines advisory review outcome using deterministic priority hierarchy."""
        top_reasons: List[str] = []
        conditions_to_change: List[str] = []
        unresolved_issues: List[str] = []
        risk_components: Dict[str, float] = {}

        # 1. Deterministic Risk Score Calculation
        # (Transparent points: Missing doc = 25, Date mismatch = 30, Sub-limit breach = 15, Exclusion = 40)
        score = 0.0
        for f in analysis_result.fraud_signals:
            if f.severity == FindingSeverity.CRITICAL:
                score += 40.0
                risk_components[f.title] = 40.0
            elif f.severity == FindingSeverity.HIGH:
                score += 25.0
                risk_components[f.title] = 25.0
            elif f.severity == FindingSeverity.MEDIUM:
                score += 15.0
                risk_components[f.title] = 15.0
            else:
                score += 5.0
                risk_components[f.title] = 5.0

        if reviewer_summary.has_unresolved_uncertainties:
            score += 10.0
            risk_components["Unresolved Clause Ambiguity"] = 10.0

        final_risk_score = min(100.0, score)

        # 2. Priority Hierarchy Gate Execution
        # Hierarchy priorities (highest first):
        #   Level 1: Verified Objective Blockers (exclusion, waiting period) → DO_NOT_TAKE
        #   Level 2: Missing Critical Documents → REVIEW_REQUIRED (unless overridden by Level 1)
        #   Level 3: Material Contradictions → REVIEW_REQUIRED
        #   Level 4: Unresolved Ambiguities / Fallback → REVIEW_REQUIRED
        #   Level 5: All clear → TAKE

        # Hierarchy Level 1: Verified Objective Blockers → DO_NOT_TAKE
        # (These are hard policy violations that cannot be remedied by submitting more documents)
        calcs = analysis_result.calculations
        if calcs.is_exclusion_violated:
            top_reasons.append(
                f"Claim contains procedure explicitly excluded under verified policy terms (${calcs.exclusion_deduction:,.2f})."
            )
            conditions_to_change.append("Provide physician certification establishing procedure was medically non-elective reconstructive surgery.")
            if analysis_result.missing_documents:
                for doc in analysis_result.missing_documents:
                    unresolved_issues.append(f"Missing mandatory document: {doc}")
                    conditions_to_change.append(f"Submit certified copy of {doc}")
                top_reasons.append(
                    f"Additionally, {len(analysis_result.missing_documents)} required document(s) remain outstanding."
                )
            return RecommendationVerdict(
                verdict=AdvisoryVerdict.DO_NOT_TAKE,
                risk_score=final_risk_score,
                risk_score_components=risk_components,
                top_reasons=top_reasons,
                conditions_to_change_verdict=conditions_to_change,
                missing_documents=analysis_result.missing_documents,
                unresolved_issues=unresolved_issues + ["Verified policy exclusion breach"],
                approved_clause_refs=reviewer_summary.approved_clause_references,
                rejected_clause_refs=[r.clause_reference for r in reviewer_summary.rejected_rules],
                uncertain_clause_refs=[r.clause_reference for r in reviewer_summary.uncertain_rules],
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                human_review_required=True,
            )

        if calcs.is_waiting_period_violated:
            top_reasons.append(
                f"Loss occurred {calcs.days_since_policy_inception} days after inception, breaching mandatory {calcs.waiting_period_days_required}-day waiting period."
            )
            conditions_to_change.append("Demonstrate unbroken prior coverage continuity or emergency accidental exemption.")
            if analysis_result.missing_documents:
                for doc in analysis_result.missing_documents:
                    unresolved_issues.append(f"Missing mandatory document: {doc}")
                    conditions_to_change.append(f"Submit certified copy of {doc}")
                top_reasons.append(
                    f"Additionally, {len(analysis_result.missing_documents)} required document(s) remain outstanding."
                )
            return RecommendationVerdict(
                verdict=AdvisoryVerdict.DO_NOT_TAKE,
                risk_score=final_risk_score,
                risk_score_components=risk_components,
                top_reasons=top_reasons,
                conditions_to_change_verdict=conditions_to_change,
                missing_documents=analysis_result.missing_documents,
                unresolved_issues=unresolved_issues + ["Verified waiting period violation"],
                approved_clause_refs=reviewer_summary.approved_clause_references,
                rejected_clause_refs=[r.clause_reference for r in reviewer_summary.rejected_rules],
                uncertain_clause_refs=[r.clause_reference for r in reviewer_summary.uncertain_rules],
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                human_review_required=True,
            )

        # Hierarchy Level 2: Missing Critical Documents → REVIEW_REQUIRED
        # (Only reached if no hard blockers from Level 1)
        if analysis_result.missing_documents:
            for doc in analysis_result.missing_documents:
                unresolved_issues.append(f"Missing mandatory document: {doc}")
                conditions_to_change.append(f"Submit certified copy of {doc}")
            top_reasons.append(
                f"Claim is incomplete: missing {len(analysis_result.missing_documents)} required document(s)."
            )
            return RecommendationVerdict(
                verdict=AdvisoryVerdict.REVIEW_REQUIRED,
                risk_score=final_risk_score,
                risk_score_components=risk_components,
                top_reasons=top_reasons,
                conditions_to_change_verdict=conditions_to_change,
                missing_documents=analysis_result.missing_documents,
                unresolved_issues=unresolved_issues,
                approved_clause_refs=reviewer_summary.approved_clause_references,
                rejected_clause_refs=[r.clause_reference for r in reviewer_summary.rejected_rules],
                uncertain_clause_refs=[r.clause_reference for r in reviewer_summary.uncertain_rules],
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                human_review_required=True,
            )

        # Hierarchy Level 3: Material Contradictions (e.g. Invoice date precedes incident date)
        if analysis_result.material_contradictions_found:
            unresolved_issues.append("Document timeline contradiction detected")
            top_reasons.append("Unresolved date mismatch between medical bill and declared incident date.")
            conditions_to_change.append("Obtain written clarification from hospital on admission timestamp.")
            return RecommendationVerdict(
                verdict=AdvisoryVerdict.REVIEW_REQUIRED,
                risk_score=final_risk_score,
                risk_score_components=risk_components,
                top_reasons=top_reasons,
                conditions_to_change_verdict=conditions_to_change,
                missing_documents=[],
                unresolved_issues=unresolved_issues,
                approved_clause_refs=reviewer_summary.approved_clause_references,
                rejected_clause_refs=[r.clause_reference for r in reviewer_summary.rejected_rules],
                uncertain_clause_refs=[r.clause_reference for r in reviewer_summary.uncertain_rules],
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                human_review_required=True,
            )

        # Hierarchy Level 4: Unresolved Policy Ambiguities or Fallback Limitation → REVIEW_REQUIRED
        if reviewer_summary.has_unresolved_uncertainties or fallback_used:
            reason = "Policy clause wording is ambiguous and requires human legal interpretation."
            if fallback_used:
                reason = f"Automated analysis executed under model fallback ({fallback_reason}); manual confirmation needed."
            top_reasons.append(reason)
            conditions_to_change.append("Senior claims assessor to review applicability of uncertain clauses.")
            return RecommendationVerdict(
                verdict=AdvisoryVerdict.REVIEW_REQUIRED,
                risk_score=final_risk_score,
                risk_score_components=risk_components,
                top_reasons=top_reasons,
                conditions_to_change_verdict=conditions_to_change,
                missing_documents=[],
                unresolved_issues=[reason],
                approved_clause_refs=reviewer_summary.approved_clause_references,
                rejected_clause_refs=[r.clause_reference for r in reviewer_summary.rejected_rules],
                uncertain_clause_refs=[r.clause_reference for r in reviewer_summary.uncertain_rules],
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                human_review_required=True,
            )

        # Hierarchy Level 5: All checks passed -> TAKE
        top_reasons.append("Claim is fully supported with itemized evidence.")
        top_reasons.append(
            f"Adjudicated net eligible amount of ${calcs.net_eligible_amount:,.2f} complies with all applicable policy rules."
        )
        if calcs.room_excess_deduction > 0.0:
            top_reasons.append(
                f"Calculated standard sub-limit deduction of ${calcs.room_excess_deduction:,.2f} on excess room rent."
            )

        return RecommendationVerdict(
            verdict=AdvisoryVerdict.TAKE,
            risk_score=final_risk_score,
            risk_score_components=risk_components,
            top_reasons=top_reasons,
            conditions_to_change_verdict=["None. Ready for positive human settlement approval."],
            missing_documents=[],
            unresolved_issues=[],
            approved_clause_refs=reviewer_summary.approved_clause_references,
            rejected_clause_refs=[r.clause_reference for r in reviewer_summary.rejected_rules],
            uncertain_clause_refs=[],
            fallback_used=False,
            fallback_reason=None,
            human_review_required=False,
        )
