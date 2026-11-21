from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload
from backend.models.policy import Policy, PolicyClause
from backend.schemas.policy import PolicyCreate, PolicyUpdate, PolicyClauseCreate


def get_policy(db: Session, policy_id: int) -> Optional[Policy]:
    """Retrieve policy by primary key ID with loaded clauses."""
    stmt = (
        select(Policy)
        .options(joinedload(Policy.clauses))
        .where(Policy.id == policy_id)
    )
    return db.scalars(stmt).unique().first()


def get_policy_by_number(db: Session, policy_number: str) -> Optional[Policy]:
    """Retrieve policy by unique policy number with loaded clauses."""
    stmt = (
        select(Policy)
        .options(joinedload(Policy.clauses))
        .where(Policy.policy_number == policy_number)
    )
    return db.scalars(stmt).unique().first()


def get_policies(
    db: Session, skip: int = 0, limit: int = 50
) -> Tuple[List[Policy], int]:
    """Retrieve paginated policies and the total count."""
    count_stmt = select(func.count(Policy.id))
    total = db.scalar(count_stmt) or 0

    stmt = (
        select(Policy)
        .options(joinedload(Policy.clauses))
        .order_by(Policy.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = list(db.scalars(stmt).unique().all())
    return items, total


def create_policy(db: Session, policy_in: PolicyCreate) -> Policy:
    """Create a new policy record with optional initial clauses."""
    policy_data = policy_in.model_dump(exclude={"clauses"})
    policy = Policy(**policy_data)
    db.add(policy)
    db.flush()  # Populates policy.id

    if policy_in.clauses:
        for clause_in in policy_in.clauses:
            clause = PolicyClause(
                policy_id=policy.id,
                **clause_in.model_dump(),
            )
            db.add(clause)

    db.commit()
    db.refresh(policy)
    return policy


def update_policy(
    db: Session, db_policy: Policy, policy_update: PolicyUpdate
) -> Policy:
    """Update fields on an existing policy."""
    update_data = policy_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_policy, field, value)

    db.commit()
    db.refresh(db_policy)
    return db_policy


def delete_policy(db: Session, db_policy: Policy) -> None:
    """Delete a policy and all associated clauses and cascade."""
    db.delete(db_policy)
    db.commit()


def add_clause_to_policy(
    db: Session, policy_id: int, clause_in: PolicyClauseCreate
) -> PolicyClause:
    """Add a new clause to an existing policy."""
    clause = PolicyClause(
        policy_id=policy_id,
        **clause_in.model_dump(),
    )
    db.add(clause)
    db.commit()
    db.refresh(clause)
    return clause
