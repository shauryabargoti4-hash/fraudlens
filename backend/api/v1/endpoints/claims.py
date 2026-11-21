import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.core.database import get_db
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
from backend.schemas.claim import (
    ClaimCreate,
    ClaimUpdate,
    ClaimResponse,
    ClaimDocumentCreate,
    ClaimDocumentResponse,
)
from backend.schemas.finding import FindingCreate, FindingResponse
from backend.schemas.common import PaginatedResponse, MessageResponse

router = APIRouter()


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
