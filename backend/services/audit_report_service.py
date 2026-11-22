"""Audit Report Generation and Persistence Service for ClauseGuard.

Synthesizes structured claim analysis reports, persists discrepancy findings,
and records immutable audit log events in SQLite.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.core.logging_config import logger
from backend.models.enums import RecommendationType, AdvisoryVerdict, FindingType, FindingSeverity
from backend.models.report import AnalysisReport, AuditLog
from backend.models.finding import DiscrepancyFinding
from backend.services.analyzer_calculator import AnalysisCalculationResult, DiscrepancyItem, PolicyLoopholeItem, CalculationSummary
from backend.services.claim_retrieval_service import ClaimEvidencePackage
from backend.services.clause_reviewer import ReviewerSummary
from backend.services.recommendation_gate import RecommendationVerdict


class ComprehensiveAnalysisReport(BaseModel):
    """Complete synthesized analysis response schema."""

    report_id: Optional[int] = None
    claim_id: int
    policy_id: int
    claimant_name: str
    policy_number: str
    verdict: AdvisoryVerdict
    recommendation: RecommendationType
    overall_risk_score: float
    confidence_score: float
    executive_summary: str
    findings_count: int
    top_reasons: List[str] = Field(default_factory=list)
    conditions_to_change_verdict: List[str] = Field(default_factory=list)
    missing_documents: List[str] = Field(default_factory=list)
    unresolved_issues: List[str] = Field(default_factory=list)
    approved_clause_refs: List[str] = Field(default_factory=list)
    calculations: CalculationSummary
    fraud_signals: List[DiscrepancyItem] = Field(default_factory=list)
    policy_loopholes: List[PolicyLoopholeItem] = Field(default_factory=list)
    human_review_required: bool = True
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    agent_trace: dict = Field(default_factory=dict)


def map_verdict_to_recommendation_type(verdict: AdvisoryVerdict) -> RecommendationType:
    """Maps AdvisoryVerdict enum to database RecommendationType enum."""
    if verdict == AdvisoryVerdict.TAKE:
        return RecommendationType.TAKE
    elif verdict == AdvisoryVerdict.DO_NOT_TAKE:
        return RecommendationType.DO_NOT_TAKE
    return RecommendationType.REVIEW_REQUIRED


class AuditReportService:
    """Builds and commits structured analysis reports, findings, and audit trails."""

    def build_report(
        self,
        evidence: ClaimEvidencePackage,
        reviewer_summary: ReviewerSummary,
        analysis_result: AnalysisCalculationResult,
        verdict: RecommendationVerdict,
    ) -> ComprehensiveAnalysisReport:
        """Synthesizes all pipeline outputs into a unified report container."""
        calcs = analysis_result.calculations
        exec_summary = (
            f"Advisory Review Verdict: {verdict.verdict.value}. "
            f"Claimed ${calcs.claimed_amount:,.2f}; Net Eligible: ${calcs.net_eligible_amount:,.2f} "
            f"(Deductions: ${calcs.total_non_eligible_amount:,.2f}). "
            f"{len(analysis_result.fraud_signals)} discrepancy finding(s), "
            f"{len(analysis_result.policy_loopholes)} policy loophole(s) noted."
        )

        trace_data = {
            "verdict": verdict.verdict.value,
            "risk_score_components": verdict.risk_score_components,
            "top_reasons": verdict.top_reasons,
            "conditions_to_change_verdict": verdict.conditions_to_change_verdict,
            "missing_documents": verdict.missing_documents,
            "unresolved_issues": verdict.unresolved_issues,
            "approved_clause_refs": verdict.approved_clause_refs,
            "calculation_steps": calcs.calculation_steps,
            "fallback_used": verdict.fallback_used,
            "fallback_reason": verdict.fallback_reason,
            "evidence_counts": {
                "policy_clauses": len(evidence.policy_chunks),
                "invoices": len(evidence.invoice_chunks),
                "claim_forms": len(evidence.claim_form_chunks),
            },
        }

        rec_type = map_verdict_to_recommendation_type(verdict.verdict)

        return ComprehensiveAnalysisReport(
            claim_id=evidence.claim_id,
            policy_id=evidence.policy_id,
            claimant_name=evidence.claimant_name,
            policy_number=evidence.policy_number,
            verdict=verdict.verdict,
            recommendation=rec_type,
            overall_risk_score=verdict.risk_score or 0.0,
            confidence_score=0.95 if not verdict.fallback_used else 0.80,
            executive_summary=exec_summary,
            findings_count=len(analysis_result.fraud_signals),
            top_reasons=verdict.top_reasons,
            conditions_to_change_verdict=verdict.conditions_to_change_verdict,
            missing_documents=verdict.missing_documents,
            unresolved_issues=verdict.unresolved_issues,
            approved_clause_refs=verdict.approved_clause_refs,
            calculations=calcs,
            fraud_signals=analysis_result.fraud_signals,
            policy_loopholes=analysis_result.policy_loopholes,
            human_review_required=verdict.human_review_required,
            fallback_used=verdict.fallback_used,
            fallback_reason=verdict.fallback_reason,
            agent_trace=trace_data,
        )

    def persist_report(
        self,
        db: Session,
        report_data: ComprehensiveAnalysisReport,
    ) -> AnalysisReport:
        """Persists the AnalysisReport, DiscrepancyFindings, and AuditLog to SQLite."""
        # 1. Format loophole summary
        loophole_text = None
        if report_data.policy_loopholes:
            loophole_text = "\n".join(
                [f"[{lh.clause_reference}] {lh.loophole_type}: {lh.description}" for lh in report_data.policy_loopholes]
            )

        # 2. Persist AnalysisReport
        db_report = AnalysisReport(
            claim_id=report_data.claim_id,
            overall_risk_score=report_data.overall_risk_score,
            recommendation=report_data.recommendation,
            confidence_score=report_data.confidence_score,
            executive_summary=report_data.executive_summary,
            findings_count=report_data.findings_count,
            loophole_analysis=loophole_text,
            agent_trace=report_data.agent_trace,
        )
        db.add(db_report)
        db.flush()

        report_data.report_id = db_report.id

        # 3. Persist Discrepancy Findings
        for f in report_data.fraud_signals:
            db_finding = DiscrepancyFinding(
                claim_id=report_data.claim_id,
                finding_type=f.finding_type,
                severity=f.severity,
                title=f.title,
                description=f.description,
                evidence_snippet=f.evidence_snippet,
                policy_reference=f.policy_reference,
                suggested_action=f.suggested_action,
            )
            db.add(db_finding)

        # 4. Record Immutable AuditLog Event
        audit = AuditLog(
            entity_type="claim",
            entity_id=str(report_data.claim_id),
            action="analysis_completed",
            details=(
                f"Advisory verdict: {report_data.verdict.value}; Risk Score: {report_data.overall_risk_score}; "
                f"Findings: {report_data.findings_count}; Net Eligible: ${report_data.calculations.net_eligible_amount:,.2f}"
            ),
        )
        db.add(audit)

        db.commit()
        db.refresh(db_report)

        logger.info(
            f"Successfully persisted AnalysisReport ID={db_report.id} for Claim {report_data.claim_id} "
            f"with verdict {report_data.verdict.value}."
        )

        return db_report
