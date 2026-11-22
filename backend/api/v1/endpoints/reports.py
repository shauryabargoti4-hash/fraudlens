"""Reports and PDF Export Endpoints for ClauseGuard."""

import datetime
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.logging_config import logger
from backend.core.rbac import require_role, get_current_user_name, get_current_user_role
from backend.models.enums import UserRole, RecommendationType, AdvisoryVerdict
from backend.models.report import AnalysisReport, AuditLog
from backend.models.claim import Claim
from backend.models.policy import Policy
from backend.models.finding import DiscrepancyFinding
from backend.reporting.pdf_exporter import get_pdf_exporter
from backend.schemas.reporting import ReportOverrideRequest, ReportOverrideResponse

router = APIRouter()


@router.get("/{report_id}/export/pdf", summary="Export Executive Audit Report as PDF")
def export_report_pdf(
    report_id: int,
    db: Session = Depends(get_db),
):
    """Generates and streams an executive-grade, regulator-ready PDF audit report."""
    report = db.query(AnalysisReport).filter(AnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis report with ID {report_id} does not exist.",
        )

    claim = db.query(Claim).filter(Claim.id == report.claim_id).first()
    policy = db.query(Policy).filter(Policy.id == claim.policy_id).first() if claim else None
    findings = db.query(DiscrepancyFinding).filter(DiscrepancyFinding.claim_id == report.claim_id).all()
    audit_logs = (
        db.query(AuditLog)
        .filter(
            ((AuditLog.entity_type == "claim") & (AuditLog.entity_id == str(report.claim_id)))
            | ((AuditLog.entity_type == "report") & (AuditLog.entity_id == str(report.id)))
        )
        .order_by(AuditLog.created_at.asc())
        .all()
    )

    exporter = get_pdf_exporter()
    try:
        pdf_bytes = exporter.generate_pdf(
            report=report,
            claim=claim,
            policy=policy,
            findings=findings,
            audit_logs=audit_logs,
        )
    except Exception as e:
        logger.exception(f"Failed to render PDF for Report {report_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate executive PDF report.",
        )

    filename = f"ClauseGuard_Audit_Report_{report_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf",
        },
    )


@router.get("/claim/{claim_id}/export/pdf", summary="Export Latest PDF Report by Claim ID")
def export_latest_claim_report_pdf(
    claim_id: int,
    db: Session = Depends(get_db),
):
    """Locates the most recent AnalysisReport for a claim and exports it as a PDF."""
    report = (
        db.query(AnalysisReport)
        .filter(AnalysisReport.claim_id == claim_id)
        .order_by(AnalysisReport.id.desc())
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis report found for Claim ID {claim_id}.",
        )
    return export_report_pdf(report_id=report.id, db=db)


@router.post(
    "/{report_id}/override",
    response_model=ReportOverrideResponse,
    summary="Adjudicator Digital Sign-Off and Verdict Override (RBAC: Senior Adjudicator)",
)
def override_report_verdict(
    report_id: int,
    payload: ReportOverrideRequest,
    db: Session = Depends(get_db),
    role: UserRole = Depends(require_role(UserRole.SENIOR_ADJUDICATOR)),
    caller_name: str = Depends(get_current_user_name),
):
    """Enforces Senior Adjudicator privileges to record a formal verdict override."""
    report = db.query(AnalysisReport).filter(AnalysisReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis report with ID {report_id} does not exist.",
        )

    # Extract original verdict
    trace = dict(report.agent_trace or {})
    original_verdict = trace.get("verdict", report.recommendation.value.upper() if hasattr(report.recommendation, "value") else str(report.recommendation).upper())
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Record override metadata
    override_record = {
        "original_verdict": original_verdict,
        "final_verdict": payload.final_verdict.value,
        "adjudicator_name": payload.adjudicator_name or caller_name,
        "justification": payload.justification,
        "timestamp": now_str,
    }

    trace["override"] = override_record
    report.agent_trace = trace

    # Update database recommendation mapping if applicable
    if payload.final_verdict == AdvisoryVerdict.TAKE:
        report.recommendation = RecommendationType.TAKE
    elif payload.final_verdict == AdvisoryVerdict.DO_NOT_TAKE:
        report.recommendation = RecommendationType.DO_NOT_TAKE
    else:
        report.recommendation = RecommendationType.REVIEW_REQUIRED

    # Add immutable AuditLog entry
    audit = AuditLog(
        entity_type="report",
        entity_id=str(report.id),
        action="verdict_overridden",
        details=(
            f"Verdict overridden from {original_verdict} to {payload.final_verdict.value} by "
            f"{payload.adjudicator_name}. Justification: {payload.justification}"
        ),
    )
    db.add(audit)
    db.commit()
    db.refresh(report)

    logger.info(
        f"Report {report.id} overridden by {payload.adjudicator_name} -> {payload.final_verdict.value}."
    )

    return ReportOverrideResponse(
        report_id=report.id,
        claim_id=report.claim_id,
        original_verdict=original_verdict,
        final_verdict=payload.final_verdict.value,
        adjudicator_name=payload.adjudicator_name,
        justification=payload.justification,
        timestamp=now_str,
    )
