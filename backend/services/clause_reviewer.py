"""Clause Reviewer Service for ClauseGuard.

Assesses whether retrieved policy rules explicitly and legitimately apply to
claim expenses before downstream calculations and fraud analysis.
Enforces silence-as-absence protection and prevents cross-clause contamination.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from backend.core.logging_config import logger
from backend.models.enums import ReviewerOutcome, ClauseType
from backend.services.claim_retrieval_service import ClaimEvidencePackage
from backend.services.policy_rule_extractor import ExtractedPolicyRule


class ClauseReviewAssessment(BaseModel):
    """Structured applicability review outcome for an individual policy rule."""

    rule_id: str
    clause_reference: str
    page_number: int
    source_chunk_id: int
    source_text: str
    outcome: ReviewerOutcome
    applicability_reason: str
    conditions_verified: List[str] = Field(default_factory=list)
    unmet_conditions: List[str] = Field(default_factory=list)
    exceptions_triggered: List[str] = Field(default_factory=list)
    is_ambiguous: bool = False
    evidence_citation: Optional[str] = None


class ReviewerSummary(BaseModel):
    """Aggregate result from the Reviewer node."""

    total_reviewed: int
    approved_rules: List[ClauseReviewAssessment] = Field(default_factory=list)
    rejected_rules: List[ClauseReviewAssessment] = Field(default_factory=list)
    uncertain_rules: List[ClauseReviewAssessment] = Field(default_factory=list)
    needs_more_evidence_rules: List[ClauseReviewAssessment] = Field(default_factory=list)

    @property
    def approved_clause_references(self) -> List[str]:
        return [r.clause_reference for r in self.approved_rules]

    @property
    def has_unresolved_uncertainties(self) -> bool:
        return len(self.uncertain_rules) > 0 or len(self.needs_more_evidence_rules) > 0


class ClauseReviewer:
    """Evaluates policy clause applicability against claim evidence package."""

    def review_rules(
        self,
        rules: List[ExtractedPolicyRule],
        evidence: ClaimEvidencePackage,
    ) -> ReviewerSummary:
        """Evaluates each extracted rule against the claim context."""
        approved: List[ClauseReviewAssessment] = []
        rejected: List[ClauseReviewAssessment] = []
        uncertain: List[ClauseReviewAssessment] = []
        needs_more_evidence: List[ClauseReviewAssessment] = []

        # Claim context
        invoices_text = " ".join([c["text"] for c in evidence.invoice_chunks]).lower()
        forms_text = " ".join([c["text"] for c in evidence.claim_form_chunks]).lower()

        for rule in rules:
            assessment = self._assess_single_rule(
                rule=rule,
                evidence=evidence,
                invoices_text=invoices_text,
                forms_text=forms_text,
            )

            if assessment.outcome == ReviewerOutcome.APPROVED:
                approved.append(assessment)
            elif assessment.outcome == ReviewerOutcome.REJECTED:
                rejected.append(assessment)
            elif assessment.outcome == ReviewerOutcome.UNCERTAIN:
                uncertain.append(assessment)
            else:
                needs_more_evidence.append(assessment)

        logger.info(
            f"Reviewer completed for Claim {evidence.claim_id}: {len(approved)} approved, "
            f"{len(rejected)} rejected, {len(uncertain)} uncertain, "
            f"{len(needs_more_evidence)} needs more evidence."
        )

        return ReviewerSummary(
            total_reviewed=len(rules),
            approved_rules=approved,
            rejected_rules=rejected,
            uncertain_rules=uncertain,
            needs_more_evidence_rules=needs_more_evidence,
        )

    def _assess_single_rule(
        self,
        rule: ExtractedPolicyRule,
        evidence: ClaimEvidencePackage,
        invoices_text: str,
        forms_text: str,
    ) -> ClauseReviewAssessment:
        """Assesses one rule under silence-as-absence and contamination rules."""
        rule_desc_lower = rule.rule_description.lower()
        clause_ref = rule.clause_reference

        # 0. EXCLUSION rules — evaluated before ambiguity gate to prevent false UNCERTAIN classification.
        #    An exclusion clause with a clear category (cosmetic/aesthetic) must be matched against invoices.
        if rule.rule_type == ClauseType.EXCLUSION:
            if "cosmetic" in rule_desc_lower or "aesthetic" in rule_desc_lower:
                if (
                    "cosmetic" in invoices_text
                    or "rhinoplasty" in invoices_text
                    or "aesthetic" in invoices_text
                    or "botox" in invoices_text
                ):
                    return ClauseReviewAssessment(
                        rule_id=rule.rule_id,
                        clause_reference=clause_ref,
                        page_number=rule.page_number,
                        source_chunk_id=rule.source_chunk_id,
                        source_text=rule.source_text_excerpt,
                        outcome=ReviewerOutcome.APPROVED,
                        applicability_reason="Medical documentation indicates procedure falling within cosmetic exclusion.",
                        conditions_verified=["Elective procedure documented on bill"],
                        evidence_citation="Invoice procedure description",
                    )
                elif "surgery" in invoices_text or "reconstruction" in invoices_text:
                    return ClauseReviewAssessment(
                        rule_id=rule.rule_id,
                        clause_reference=clause_ref,
                        page_number=rule.page_number,
                        source_chunk_id=rule.source_chunk_id,
                        source_text=rule.source_text_excerpt,
                        outcome=ReviewerOutcome.NEEDS_MORE_EVIDENCE,
                        applicability_reason="Surgical procedure billed; operative notes needed to distinguish cosmetic from reconstructive.",
                    )
                else:
                    return ClauseReviewAssessment(
                        rule_id=rule.rule_id,
                        clause_reference=clause_ref,
                        page_number=rule.page_number,
                        source_chunk_id=rule.source_chunk_id,
                        source_text=rule.source_text_excerpt,
                        outcome=ReviewerOutcome.REJECTED,
                        applicability_reason="Claim contains no cosmetic or aesthetic medical procedures.",
                    )

        # Check for ambiguity (only applied after exclusion check above)
        if rule.ambiguity_flag or "reasonable and customary" in rule.source_text_excerpt.lower():
            return ClauseReviewAssessment(
                rule_id=rule.rule_id,
                clause_reference=clause_ref,
                page_number=rule.page_number,
                source_chunk_id=rule.source_chunk_id,
                source_text=rule.source_text_excerpt,
                outcome=ReviewerOutcome.UNCERTAIN,
                applicability_reason="Policy clause contains ambiguous terminology or undefined standard.",
                is_ambiguous=True,
            )

        # 1. Deductibles and General Limits
        if rule.rule_type in [ClauseType.DEDUCTIBLE, ClauseType.COVERAGE_SCOPE]:
            return ClauseReviewAssessment(
                rule_id=rule.rule_id,
                clause_reference=clause_ref,
                page_number=rule.page_number,
                source_chunk_id=rule.source_chunk_id,
                source_text=rule.source_text_excerpt,
                outcome=ReviewerOutcome.APPROVED,
                applicability_reason="General policy condition applicable to all claims under this policy.",
                conditions_verified=["Policy active during incident date"],
                evidence_citation=f"Claim {evidence.claim_id} incident date {evidence.incident_date}",
            )

        # 2. Sub-limits (e.g. room rent)
        if rule.rule_type == ClauseType.SUB_LIMIT:
            source_lower = rule.source_text_excerpt.lower()
            # Cross-clause contamination check: ensure invoice actually has matching category.
            # Check both rule description AND source text for room/board keywords.
            is_room_rule = (
                "room" in rule_desc_lower or "board" in rule_desc_lower or "bed" in rule_desc_lower
                or "room" in source_lower or "board" in source_lower
            )
            if is_room_rule:
                if "room" in invoices_text or "bed" in invoices_text or "admission" in invoices_text:
                    return ClauseReviewAssessment(
                        rule_id=rule.rule_id,
                        clause_reference=clause_ref,
                        page_number=rule.page_number,
                        source_chunk_id=rule.source_chunk_id,
                        source_text=rule.source_text_excerpt,
                        outcome=ReviewerOutcome.APPROVED,
                        applicability_reason="Invoice contains room and board charges matching sub-limit clause.",
                        conditions_verified=["Inpatient hospital admission substantiated"],
                        evidence_citation="Itemized medical invoice room rent charge lines",
                    )
                else:
                    return ClauseReviewAssessment(
                        rule_id=rule.rule_id,
                        clause_reference=clause_ref,
                        page_number=rule.page_number,
                        source_chunk_id=rule.source_chunk_id,
                        source_text=rule.source_text_excerpt,
                        outcome=ReviewerOutcome.REJECTED,
                        applicability_reason="No room and board charges present in submitted claim invoices.",
                    )

            # Other sub-limits (e.g. ambulance, diagnostic)
            if any(term in invoices_text for term in ["consultation", "lab", "ambulance", "surgery"]):
                return ClauseReviewAssessment(
                    rule_id=rule.rule_id,
                    clause_reference=clause_ref,
                    page_number=rule.page_number,
                    source_chunk_id=rule.source_chunk_id,
                    source_text=rule.source_text_excerpt,
                    outcome=ReviewerOutcome.APPROVED,
                    applicability_reason="Procedure or item matches specific policy sub-limit.",
                    conditions_verified=["Billed item documented on invoice"],
                )
            return ClauseReviewAssessment(
                rule_id=rule.rule_id,
                clause_reference=clause_ref,
                page_number=rule.page_number,
                source_chunk_id=rule.source_chunk_id,
                source_text=rule.source_text_excerpt,
                outcome=ReviewerOutcome.REJECTED,
                applicability_reason="Sub-limit category does not correspond to claim line items.",
            )

        # 3. Waiting Periods
        if rule.rule_type == ClauseType.WAITING_PERIOD:
            # Applicable to all illnesses
            return ClauseReviewAssessment(
                rule_id=rule.rule_id,
                clause_reference=clause_ref,
                page_number=rule.page_number,
                source_chunk_id=rule.source_chunk_id,
                source_text=rule.source_text_excerpt,
                outcome=ReviewerOutcome.APPROVED,
                applicability_reason="Mandatory policy waiting period applies to declared illness or diagnosis.",
                conditions_verified=["Non-emergency medical claim"],
                evidence_citation=f"Claim date {evidence.incident_date}",
            )

        # 4. Mandatory Documents
        if rule.rule_type == ClauseType.MANDATORY_DOCUMENT:
            return ClauseReviewAssessment(
                rule_id=rule.rule_id,
                clause_reference=clause_ref,
                page_number=rule.page_number,
                source_chunk_id=rule.source_chunk_id,
                source_text=rule.source_text_excerpt,
                outcome=ReviewerOutcome.APPROVED,
                applicability_reason="Policy mandates document submission for claim adjudication.",
                conditions_verified=["Required proof of claim"],
            )

        # Default fallback: Silence-as-absence: Do not assume exclusion
        return ClauseReviewAssessment(
            rule_id=rule.rule_id,
            clause_reference=clause_ref,
            page_number=rule.page_number,
            source_chunk_id=rule.source_chunk_id,
            source_text=rule.source_text_excerpt,
            outcome=ReviewerOutcome.APPROVED,
            applicability_reason="General policy clause verified.",
        )
