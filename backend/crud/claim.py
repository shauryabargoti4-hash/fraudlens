from typing import List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload
from backend.models.claim import Claim, ClaimDocument
from backend.models.finding import DiscrepancyFinding
from backend.schemas.claim import ClaimCreate, ClaimUpdate, ClaimDocumentCreate
from backend.schemas.finding import FindingCreate


def get_claim(db: Session, claim_id: int) -> Optional[Claim]:
    """Retrieve a claim by ID with documents and findings loaded."""
    stmt = (
        select(Claim)
        .options(
            joinedload(Claim.documents),
            joinedload(Claim.findings),
            joinedload(Claim.reports),
        )
        .where(Claim.id == claim_id)
    )
    return db.scalars(stmt).unique().first()


def get_claim_by_number(db: Session, claim_number: str) -> Optional[Claim]:
    """Retrieve a claim by its unique claim number."""
    stmt = (
        select(Claim)
        .options(
            joinedload(Claim.documents),
            joinedload(Claim.findings),
        )
        .where(Claim.claim_number == claim_number)
    )
    return db.scalars(stmt).unique().first()


def get_claims(
    db: Session, skip: int = 0, limit: int = 50, policy_id: Optional[int] = None
) -> Tuple[List[Claim], int]:
    """Retrieve paginated claims, optionally filtered by policy_id."""
    count_stmt = select(func.count(Claim.id))
    if policy_id is not None:
        count_stmt = count_stmt.where(Claim.policy_id == policy_id)
    total = db.scalar(count_stmt) or 0

    stmt = (
        select(Claim)
        .options(joinedload(Claim.documents))
        .order_by(Claim.created_at.desc())
    )
    if policy_id is not None:
        stmt = stmt.where(Claim.policy_id == policy_id)

    stmt = stmt.offset(skip).limit(limit)
    items = list(db.scalars(stmt).unique().all())
    return items, total


def create_claim(db: Session, claim_in: ClaimCreate) -> Claim:
    """Create a new insurance claim."""
    claim = Claim(**claim_in.model_dump())
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim


def update_claim(db: Session, db_claim: Claim, claim_update: ClaimUpdate) -> Claim:
    """Update fields on an existing claim."""
    update_data = claim_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_claim, field, value)

    db.commit()
    db.refresh(db_claim)
    return db_claim


def delete_claim(db: Session, db_claim: Claim) -> None:
    """Delete a claim and associated documents and findings."""
    db.delete(db_claim)
    db.commit()


def add_document_to_claim(
    db: Session, claim_id: int, doc_in: ClaimDocumentCreate
) -> ClaimDocument:
    """Attach a document record to a claim."""
    doc = ClaimDocument(
        claim_id=claim_id,
        **doc_in.model_dump(),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def add_finding_to_claim(
    db: Session, finding_in: FindingCreate
) -> DiscrepancyFinding:
    """Attach an audit discrepancy finding to a claim."""
    finding = DiscrepancyFinding(**finding_in.model_dump())
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding
