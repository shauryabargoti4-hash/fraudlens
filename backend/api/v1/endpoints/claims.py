import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.logging_config import logger
from backend.crud.policy import get_policy as crud_get_policy
from backend.crud.claim import (
    create_claim as crud_create_claim,
    get_claim as crud_get_claim,
    get_claim_by_number as crud_get_claim_by_number,
    get_claims as crud_get_claims,
    update_claim as crud_update_claim,
    delete_claim as crud_delete_claim,
    add_document_to_claim as crud_add_document,
    add_finding_to_claim as crud_add_finding,
)
from backend.models.enums import AdvisoryVerdict
from backend.models.report import AnalysisReport
from backend.schemas.claim import (
    ClaimCreate,
    ClaimUpdate,
    ClaimResponse,
    ClaimDocumentCreate,
    ClaimDocumentResponse,
)
from backend.schemas.finding import FindingCreate, FindingResponse
from backend.schemas.common import PaginatedResponse, MessageResponse
from backend.schemas.reporting import (
    BatchClaimAuditRequest,
    BatchClaimAuditResponse,
    BatchClaimItemResult,
)
from backend.services.audit_report_service import ComprehensiveAnalysisReport
from backend.services.analyzer_calculator import CalculationSummary
from backend.services.llm_provider import BaseLLMProvider, get_llm_provider
from backend.services.vector_store import VectorStore, get_vector_store

router = APIRouter()


def get_llm_provider_dep() -> BaseLLMProvider:
    """Dependency provider for LLM provider."""
    return get_llm_provider()


def get_vector_store_dep() -> VectorStore:
    """Dependency provider for Vector Store."""
    return get_vector_store()


@router.post("/", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED, summary="Create a new claim")
def create_claim(claim_in: ClaimCreate, db: Session = Depends(get_db)) -> ClaimResponse:
    """Submit a new insurance claim linked to a valid policy."""
    policy = crud_get_policy(db, policy_id=claim_in.policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent Policy with ID {claim_in.policy_id} does not exist.",
        )

    existing = crud_get_claim_by_number(db, claim_number=claim_in.claim_number)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Claim with number '{claim_in.claim_number}' already exists.",
        )

    return crud_create_claim(db, claim_in=claim_in)


@router.get("/", response_model=PaginatedResponse[ClaimResponse], summary="List all claims")
def list_claims(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    policy_id: Optional[int] = Query(None, description="Filter by policy ID"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ClaimResponse]:
    """Retrieve paginated list of claims."""
    skip = (page - 1) * page_size
    items, total = crud_get_claims(db, skip=skip, limit=page_size, policy_id=policy_id)
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[ClaimResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{claim_id}", response_model=ClaimResponse, summary="Get claim by ID")
def get_claim(claim_id: int, db: Session = Depends(get_db)) -> ClaimResponse:
    """Retrieve complete claim details including documents and audit findings."""
    claim = crud_get_claim(db, claim_id=claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID {claim_id} not found.",
        )
    return claim


@router.put("/{claim_id}", response_model=ClaimResponse, summary="Update claim details")
def update_claim(
    claim_id: int,
    claim_update: ClaimUpdate,
    db: Session = Depends(get_db),
) -> ClaimResponse:
    """Update fields on an existing claim."""
    claim = crud_get_claim(db, claim_id=claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID {claim_id} not found.",
        )
    return crud_update_claim(db, db_claim=claim, claim_update=claim_update)


@router.delete("/{claim_id}", response_model=MessageResponse, summary="Delete a claim")
def delete_claim(claim_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    """Delete a claim and cascade delete associated documents and findings."""
    claim = crud_get_claim(db, claim_id=claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID {claim_id} not found.",
        )
    crud_delete_claim(db, db_claim=claim)
    return MessageResponse(message=f"Claim {claim_id} successfully deleted.")


@router.post(
    "/{claim_id}/documents",
    response_model=ClaimDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach a document to a claim",
)
def attach_document(
    claim_id: int,
    doc_in: ClaimDocumentCreate,
    db: Session = Depends(get_db),
) -> ClaimDocumentResponse:
    """Attach a document record to a claim."""
    claim = crud_get_claim(db, claim_id=claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID {claim_id} not found.",
        )
    return crud_add_document(db, claim_id=claim_id, doc_in=doc_in)


@router.post(
    "/{claim_id}/findings",
    response_model=FindingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a discrepancy finding to a claim",
)
def add_finding(
    claim_id: int,
    finding_in: FindingCreate,
    db: Session = Depends(get_db),
) -> FindingResponse:
    """Record an audit discrepancy finding for a claim."""
    if finding_in.claim_id != claim_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Route claim_id does not match payload claim_id.",
        )
    claim = crud_get_claim(db, claim_id=claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID {claim_id} not found.",
        )
    return crud_add_finding(db, finding_in=finding_in)


@router.post(
    "/{claim_id}/analyze",
    response_model=ComprehensiveAnalysisReport,
    status_code=status.HTTP_200_OK,
    summary="Trigger end-to-end AI claim analysis pipeline",
)
def trigger_claim_analysis(
    claim_id: int,
    db: Session = Depends(get_db),
    llm_provider: BaseLLMProvider = Depends(get_llm_provider_dep),
    vector_store: VectorStore = Depends(get_vector_store_dep),
) -> ComprehensiveAnalysisReport:
    """Executes the complete ClauseGuard LangGraph sequential analysis workflow on a claim."""
    claim = crud_get_claim(db, claim_id=claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID {claim_id} not found.",
        )

    policy = crud_get_policy(db, policy_id=claim.policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent Policy with ID {claim.policy_id} not found.",
        )

    try:
        from backend.workflows.claim_analysis_workflow import run_claim_analysis
        report = run_claim_analysis(
            claim_id=claim_id,
            db=db,
            llm_provider=llm_provider,
            vector_store=vector_store,
        )
        return report
    except Exception as exc:
        logger.error(f"Claim analysis pipeline execution failed for Claim {claim_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Claim analysis pipeline execution failed: {str(exc)}",
        )


@router.get(
    "/{claim_id}/analysis",
    response_model=ComprehensiveAnalysisReport,
    summary="Retrieve the latest analysis report for a claim",
)
def get_claim_analysis(
    claim_id: int,
    db: Session = Depends(get_db),
) -> ComprehensiveAnalysisReport:
    """Retrieve the most recently generated analysis report for a claim."""
    claim = crud_get_claim(db, claim_id=claim_id)
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Claim with ID {claim_id} not found.",
        )

    stmt = (
        select(AnalysisReport)
        .where(AnalysisReport.claim_id == claim_id)
        .order_by(AnalysisReport.created_at.desc())
    )
    db_report = db.scalars(stmt).first()
    if not db_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No analysis report found for Claim {claim_id}.",
        )

    trace = db_report.agent_trace or {}
    verdict_str = trace.get("verdict", "REVIEW_REQUIRED")
    verdict = AdvisoryVerdict(verdict_str) if verdict_str in [v.value for v in AdvisoryVerdict] else AdvisoryVerdict.REVIEW_REQUIRED

    calcs = CalculationSummary(
        claimed_amount=claim.claimed_amount,
        total_billed_amount=claim.claimed_amount,
        net_eligible_amount=claim.claimed_amount,
        calculation_steps=trace.get("calculation_steps", []),
    )

    policy = crud_get_policy(db, policy_id=claim.policy_id)
    policy_number = policy.policy_number if policy else "N/A"

    return ComprehensiveAnalysisReport(
        report_id=db_report.id,
        claim_id=claim_id,
        policy_id=claim.policy_id,
        claimant_name=claim.claimant_name,
        policy_number=policy_number,
        verdict=verdict,
        recommendation=db_report.recommendation,
        overall_risk_score=db_report.overall_risk_score,
        confidence_score=db_report.confidence_score,
        executive_summary=db_report.executive_summary,
        findings_count=db_report.findings_count,
        top_reasons=trace.get("top_reasons", []),
        conditions_to_change_verdict=trace.get("conditions_to_change_verdict", []),
        missing_documents=trace.get("missing_documents", []),
        unresolved_issues=trace.get("unresolved_issues", []),
        approved_clause_refs=trace.get("approved_clause_refs", []),
        calculations=calcs,
        human_review_required=verdict != AdvisoryVerdict.TAKE,
        fallback_used=trace.get("fallback_used", False),
        fallback_reason=trace.get("fallback_reason"),
        agent_trace=trace,
    )


@router.post(
    "/batch-audit",
    response_model=BatchClaimAuditResponse,
    summary="Batch Portfolio Claim Audit with Error Isolation",
)
def batch_audit_claims(
    payload: BatchClaimAuditRequest,
    db: Session = Depends(get_db),
    llm_provider: BaseLLMProvider = Depends(get_llm_provider_dep),
    vector_store: VectorStore = Depends(get_vector_store_dep),
) -> BatchClaimAuditResponse:
    """Executes the LangGraph analysis pipeline across multiple claims with strict error isolation."""
    from backend.workflows.claim_analysis_workflow import run_claim_analysis

    # 1. Determine Target Claim IDs
    target_ids = []
    if payload.claim_ids:
        target_ids = payload.claim_ids
    elif payload.policy_id:
        policy_claims = db.query(Claim.id).filter(Claim.policy_id == payload.policy_id).all()
        target_ids = [c[0] for c in policy_claims]
    else:
        # Default to all claims up to 50
        all_claims = db.query(Claim.id).limit(50).all()
        target_ids = [c[0] for c in all_claims]

    results: list[BatchClaimItemResult] = []
    verdict_counts: dict[str, int] = {}
    successful_count = 0
    failed_count = 0

    for cid in target_ids:
        claim_obj = crud_get_claim(db, claim_id=cid)
        claim_num = claim_obj.claim_number if claim_obj else f"ID-{cid}"

        if not claim_obj:
            failed_count += 1
            results.append(
                BatchClaimItemResult(
                    claim_id=cid,
                    claim_number=claim_num,
                    status="error",
                    error_message=f"Claim ID {cid} not found in database.",
                )
            )
            continue

        # Execute with complete error isolation per claim
        try:
            report = run_claim_analysis(
                claim_id=cid,
                db=db,
                llm_provider=llm_provider,
                vector_store=vector_store,
            )
            verdict_val = report.verdict.value if hasattr(report.verdict, "value") else str(report.verdict)
            verdict_counts[verdict_val] = verdict_counts.get(verdict_val, 0) + 1
            successful_count += 1

            results.append(
                BatchClaimItemResult(
                    claim_id=cid,
                    claim_number=claim_num,
                    status="success",
                    verdict=verdict_val,
                    risk_score=report.overall_risk_score,
                    report_id=report.report_id,
                )
            )
        except Exception as e:
            logger.exception(f"Batch audit failed on Claim {cid}: {e}")
            failed_count += 1
            results.append(
                BatchClaimItemResult(
                    claim_id=cid,
                    claim_number=claim_num,
                    status="error",
                    error_message=str(e),
                )
            )

    return BatchClaimAuditResponse(
        total_claims=len(target_ids),
        processed_count=len(results),
        successful_count=successful_count,
        failed_count=failed_count,
        verdict_counts=verdict_counts,
        results=results,
    )
