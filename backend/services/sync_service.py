"""Index Synchronization Service for ClauseGuard.

Synchronizes relational DocumentChunk records from SQLite into the persistent
ChromaDB vector store idempotently, recording full statistics and error provenance.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.core.config import get_settings
from backend.core.logging_config import logger
from backend.models.document_chunk import DocumentChunk
from backend.services.vector_store import VectorStore, get_vector_store


class SynchronizationReport(BaseModel):
    """Structured report returned following synchronization."""

    total_discovered: int = Field(0, description="Total DocumentChunk records found in database")
    successfully_indexed: int = Field(0, description="Number of vectors successfully upserted into ChromaDB")
    failed_chunks: int = Field(0, description="Number of chunks that failed indexing")
    skipped_chunks: int = Field(0, description="Number of chunks skipped (e.g. empty text)")
    collection_name: str = Field("", description="Target ChromaDB collection name")
    embedding_model: str = Field("", description="Embedding model or provider used")
    errors: List[str] = Field(default_factory=list, description="List of error messages if any occurred")
    is_success: bool = Field(True, description="Whether entire synchronization completed without fatal error")


def synchronize_chunks_to_vector_store(
    db: Session,
    vector_store: Optional[VectorStore] = None,
    force_reindex: bool = False,
    batch_size: int = 50,
) -> SynchronizationReport:
    """Synchronizes all DocumentChunk records from SQLite into ChromaDB.

    Idempotent: Uses deterministic vector IDs ('chunk_{id}') so re-running updates
    existing vectors without producing duplicates.
    """
    settings = get_settings()
    vs = vector_store or get_vector_store()
    collection_name = vs.collection_name
    emb_model = settings.embedding_model if settings.embedding_provider == "gemini" else f"mock_{settings.embedding_dimension}d"

    # 1. Fetch all DocumentChunk records from SQLite
    try:
        chunks = db.query(DocumentChunk).order_by(DocumentChunk.id.asc()).all()
    except Exception as e:
        logger.error(f"Failed to query DocumentChunk records from database: {e}")
        return SynchronizationReport(
            total_discovered=0,
            collection_name=collection_name,
            embedding_model=emb_model,
            is_success=False,
            errors=[f"Database query error: {str(e)}"],
        )

    total_discovered = len(chunks)
    if total_discovered == 0:
        return SynchronizationReport(
            total_discovered=0,
            successfully_indexed=0,
            collection_name=collection_name,
            embedding_model=emb_model,
            is_success=True,
        )

    # 2. Filter valid chunks
    valid_chunks: List[DocumentChunk] = []
    skipped_count = 0
    for chunk in chunks:
        if not chunk.text or not chunk.text.strip():
            skipped_count += 1
        else:
            valid_chunks.append(chunk)

    successfully_indexed = 0
    failed_count = 0
    errors: List[str] = []

    # 3. Batch upsert into ChromaDB
    for i in range(0, len(valid_chunks), batch_size):
        batch = valid_chunks[i : i + batch_size]
        try:
            count = vs.upsert_chunks(batch)
            successfully_indexed += count
        except Exception as batch_err:
            failed_count += len(batch)
            err_msg = f"Failed to index batch at offset {i}: {batch_err}"
            logger.error(err_msg)
            errors.append(err_msg)

    is_success = failed_count == 0

    report = SynchronizationReport(
        total_discovered=total_discovered,
        successfully_indexed=successfully_indexed,
        failed_chunks=failed_count,
        skipped_chunks=skipped_count,
        collection_name=collection_name,
        embedding_model=emb_model,
        errors=errors,
        is_success=is_success,
    )

    logger.info(
        f"ChromaDB synchronization complete: {successfully_indexed}/{total_discovered} chunks indexed "
        f"into '{collection_name}' (skipped={skipped_count}, failed={failed_count})"
    )

    return report
