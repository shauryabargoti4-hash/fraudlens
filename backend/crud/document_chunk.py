from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.models.document_chunk import DocumentChunk
from backend.schemas.document_chunk import DocumentChunkCreate


def create_chunk(db: Session, chunk_in: DocumentChunkCreate) -> DocumentChunk:
    """Create a single DocumentChunk record."""
    chunk = DocumentChunk(**chunk_in.model_dump())
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


def create_chunks_batch(
    db: Session, chunks_in: List[DocumentChunkCreate]
) -> List[DocumentChunk]:
    """Bulk create DocumentChunk records."""
    if not chunks_in:
        return []
    chunks = [DocumentChunk(**chunk_in.model_dump()) for chunk_in in chunks_in]
    db.add_all(chunks)
    db.commit()
    for chunk in chunks:
        db.refresh(chunk)
    return chunks


def get_chunk(db: Session, chunk_id: int) -> Optional[DocumentChunk]:
    """Retrieve chunk by primary key."""
    return db.get(DocumentChunk, chunk_id)


def get_chunks_by_document(
    db: Session, claim_document_id: int
) -> List[DocumentChunk]:
    """Retrieve all chunks belonging to a claim document, ordered by chunk_index."""
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.claim_document_id == claim_document_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    return list(db.scalars(stmt).all())


def get_chunks_by_policy(db: Session, policy_id: int) -> List[DocumentChunk]:
    """Retrieve all chunks belonging to a policy, ordered by chunk_index."""
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.policy_id == policy_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    return list(db.scalars(stmt).all())


def get_chunks_by_claim(db: Session, claim_id: int) -> List[DocumentChunk]:
    """Retrieve all chunks belonging to a claim, ordered by chunk_index."""
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.claim_id == claim_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    return list(db.scalars(stmt).all())


def delete_chunk(db: Session, chunk_id: int) -> bool:
    """Delete a chunk by ID."""
    chunk = db.get(DocumentChunk, chunk_id)
    if chunk:
        db.delete(chunk)
        db.commit()
        return True
    return False
