from pathlib import Path
from sqlalchemy.orm import Session
from backend.models.document_chunk import DocumentChunk
from backend.services.embeddings_service import MockEmbeddingProvider, EmbeddingsService
from backend.services.vector_store import VectorStore
from backend.services.sync_service import (
    synchronize_chunks_to_vector_store,
    SynchronizationReport,
)


def _seed_db_chunks(db: Session, count: int = 5):
    chunks = []
    for i in range(count):
        chunk = DocumentChunk(
            claim_document_id=1,
            policy_id=10,
            claim_id=20,
            chunk_index=i,
            clause_or_section_ref=f"SEC-{i}.1",
            page_number=1,
            text=f"Content for chunk number {i} with policy terms.",
            metadata_json={"document_type": "policy_document", "filename": f"doc_{i}.pdf"},
        )
        db.add(chunk)
    db.commit()


def test_sync_empty_database(db_session: Session, tmp_path: Path):
    chroma_dir = tmp_path / "chroma_empty"
    vs = VectorStore(
        persist_directory=chroma_dir,
        collection_name="sync_empty",
        embeddings_service=EmbeddingsService(provider=MockEmbeddingProvider(dimension=64)),
    )
    report = synchronize_chunks_to_vector_store(db_session, vector_store=vs)

    assert report.is_success is True
    assert report.total_discovered == 0
    assert report.successfully_indexed == 0
    assert report.failed_chunks == 0
    assert vs.count() == 0


def test_sync_arbitrary_chunk_count(db_session: Session, tmp_path: Path):
    _seed_db_chunks(db_session, count=7)
    chroma_dir = tmp_path / "chroma_seven"
    vs = VectorStore(
        persist_directory=chroma_dir,
        collection_name="sync_seven",
        embeddings_service=EmbeddingsService(provider=MockEmbeddingProvider(dimension=64)),
    )
    report = synchronize_chunks_to_vector_store(db_session, vector_store=vs, batch_size=3)

    assert report.is_success is True
    assert report.total_discovered == 7
    assert report.successfully_indexed == 7
    assert vs.count() == 7

    # Verify retrieval after synchronization (exact match produces identical mock vector)
    target_text = "Content for chunk number 3 with policy terms."
    results = vs.query_similar(target_text, top_k=1)
    assert len(results) == 1
    assert results[0].text == target_text
    assert results[0].clause_or_section_ref == "SEC-3.1"
    assert results[0].similarity_score is not None
    assert results[0].similarity_score > 0.99


def test_sync_idempotency_repeated_runs(db_session: Session, tmp_path: Path):
    _seed_db_chunks(db_session, count=4)
    chroma_dir = tmp_path / "chroma_idempotent"
    vs = VectorStore(
        persist_directory=chroma_dir,
        collection_name="sync_idempotent",
        embeddings_service=EmbeddingsService(provider=MockEmbeddingProvider(dimension=64)),
    )

    # First run
    report1 = synchronize_chunks_to_vector_store(db_session, vector_store=vs)
    assert report1.successfully_indexed == 4
    assert vs.count() == 4

    # Second run on same DB -> upserts in place, vector count must remain 4 (no duplicates)
    report2 = synchronize_chunks_to_vector_store(db_session, vector_store=vs)
    assert report2.successfully_indexed == 4
    assert vs.count() == 4


def test_sync_handles_skipped_empty_chunks(db_session: Session, tmp_path: Path):
    # Add valid chunk
    c1 = DocumentChunk(
        chunk_index=0,
        text="Valid chunk with content.",
        page_number=1,
    )
    # Add empty chunk
    c2 = DocumentChunk(
        chunk_index=1,
        text="   \n  ",
        page_number=1,
    )
    db_session.add_all([c1, c2])
    db_session.commit()

    chroma_dir = tmp_path / "chroma_skipped"
    vs = VectorStore(
        persist_directory=chroma_dir,
        collection_name="sync_skipped",
        embeddings_service=EmbeddingsService(provider=MockEmbeddingProvider(dimension=64)),
    )
    report = synchronize_chunks_to_vector_store(db_session, vector_store=vs)

    assert report.total_discovered == 2
    assert report.successfully_indexed == 1
    assert report.skipped_chunks == 1
    assert vs.count() == 1
