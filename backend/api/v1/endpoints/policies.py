import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.crud.policy import (
    create_policy as crud_create_policy,
    get_policy as crud_get_policy,
    get_policy_by_number as crud_get_policy_by_number,
    get_policies as crud_get_policies,
    update_policy as crud_update_policy,
    delete_policy as crud_delete_policy,
    add_clause_to_policy as crud_add_clause,
)
from backend.schemas.policy import (
    PolicyCreate,
    PolicyUpdate,
    PolicyResponse,
    PolicyClauseCreate,
    PolicyClauseResponse,
)
from backend.schemas.common import PaginatedResponse, MessageResponse

router = APIRouter()


@router.post("/", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED, summary="Create a new policy")
def create_policy(policy_in: PolicyCreate, db: Session = Depends(get_db)) -> PolicyResponse:
    """Register a new policy with optional initial clauses."""
    existing = crud_get_policy_by_number(db, policy_number=policy_in.policy_number)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Policy with number '{policy_in.policy_number}' already exists.",
        )
    return crud_create_policy(db, policy_in=policy_in)


@router.get("/", response_model=PaginatedResponse[PolicyResponse], summary="List all policies")
def list_policies(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PolicyResponse]:
    """Retrieve paginated list of policies."""
    skip = (page - 1) * page_size
    items, total = crud_get_policies(db, skip=skip, limit=page_size)
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return PaginatedResponse[PolicyResponse](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{policy_id}", response_model=PolicyResponse, summary="Get policy by ID")
def get_policy(policy_id: int, db: Session = Depends(get_db)) -> PolicyResponse:
    """Retrieve details for a single policy including its clauses."""
    policy = crud_get_policy(db, policy_id=policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found.",
        )
    return policy


@router.put("/{policy_id}", response_model=PolicyResponse, summary="Update policy details")
def update_policy(
    policy_id: int,
    policy_update: PolicyUpdate,
    db: Session = Depends(get_db),
) -> PolicyResponse:
    """Update fields on an existing policy."""
    policy = crud_get_policy(db, policy_id=policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found.",
        )
    return crud_update_policy(db, db_policy=policy, policy_update=policy_update)


@router.delete("/{policy_id}", response_model=MessageResponse, summary="Delete a policy")
def delete_policy(policy_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    """Delete a policy and cascade remove all related clauses and records."""
    policy = crud_get_policy(db, policy_id=policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found.",
        )
    crud_delete_policy(db, db_policy=policy)
    return MessageResponse(message=f"Policy {policy_id} successfully deleted.")


@router.post(
    "/{policy_id}/clauses",
    response_model=PolicyClauseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a clause to a policy",
)
def add_clause(
    policy_id: int,
    clause_in: PolicyClauseCreate,
    db: Session = Depends(get_db),
) -> PolicyClauseResponse:
    """Add an individual clause to an existing policy."""
    policy = crud_get_policy(db, policy_id=policy_id)
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Policy with ID {policy_id} not found.",
        )
    return crud_add_clause(db, policy_id=policy_id, clause_in=clause_in)
