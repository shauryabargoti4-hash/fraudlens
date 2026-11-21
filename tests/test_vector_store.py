from pathlib import Path
import pytest
from backend.models.document_chunk import DocumentChunk
from backend.services.embeddings_service import MockEmbeddingProvider, EmbeddingsService
from backend.services.vector_store import VectorStore


@pytest.fixture
def temp_vector_store(tmp_path: Path) -> VectorStore:
    """Fixture providing an isolated VectorStore pointing to a temporary test directory."""
    chroma_dir = tmp_path / "test_chroma"
    embeddings = EmbeddingsService(provider=MockEmbeddingProvider(dimension=64))
    vs = VectorStore(
        persist_directory=chroma_dir,
        collection_name="test_collection",
        embeddings_service=embeddings,
    )
    vs.reset_collection()
    return vs


def _create_sample_chunks():
    c1 = DocumentChunk(
        id=101,
        claim_document_id=1,
        policy_id=10,
        claim_id=20,
        chunk_index=0,
        clause_or_section_ref="SEC-1.1",
        page_number=1,
        text="Aggregate coverage limit is $500,000 per policy year.",
        metadata_json={"document_type": "policy_document", "filename": "policy.pdf"},
    )
    c2 = DocumentChunk(
        id=102,
        claim_document_id=1,
        policy_id=10,
        claim_id=20,
        chunk_index=1,
        clause_or_section_ref="SEC-2.1",
        page_number=1,
        text="Inpatient room and board is capped at $500 per day.",
        metadata_json={"document_type": "policy_document", "filename": "policy.pdf"},
    )
    c3 = DocumentChunk(
        id=103,
        claim_document_id=2,
        policy_id=10,
        claim_id=20,
        chunk_index=0,
        clause_or_section_ref="Line 1",
        page_number=1,
        text="Hospital room charge: 4 nights @ $600 per night equals $2,400.",
        metadata_json={"document_type": "medical_invoice", "filename": "bill.pdf"},
    )
    c4 = DocumentChunk(
        id=104,
        claim_document_id=3,
        policy_id=99,
        claim_id=88,
        chunk_index=0,
        clause_or_section_ref="SEC-AUTO-1",
        page_number=1,
        text="Automobile collision damage deductible is $1,000.",
        metadata_json={"document_type": "policy_document", "filename": "auto_policy.pdf"},
    )
    return [c1, c2, c3, c4]


def test_vector_store_initialization_and_count(temp_vector_store: VectorStore):
    assert temp_vector_store.count() == 0
    chunks = _create_sample_chunks()
    count = temp_vector_store.upsert_chunks(chunks)
    assert count == 4
    assert temp_vector_store.count() == 4


def test_upsert_chunk_idempotency(temp_vector_store: VectorStore):
    chunk = _create_sample_chunks()[0]
    # First upsert
    vec_id1 = temp_vector_store.upsert_chunk(chunk)
    assert temp_vector_store.count() == 1
    assert vec_id1 == "chunk_101"

    # Second upsert of identical chunk ID -> updates in place, does not duplicate
    vec_id2 = temp_vector_store.upsert_chunk(chunk)
    assert temp_vector_store.count() == 1
    assert vec_id2 == "chunk_101"


def test_query_similar_basic(temp_vector_store: VectorStore):
    temp_vector_store.upsert_chunks(_create_sample_chunks())

    results = temp_vector_store.query_similar("room and board rate", top_k=2)
    assert len(results) == 2
    assert all(r.chunk_id in [101, 102, 103, 104] for r in results)
    assert results[0].similarity_score is not None
    assert 0.0 <= results[0].similarity_score <= 1.0


def test_query_policy_chunks_filtering(temp_vector_store: VectorStore):
    temp_vector_store.upsert_chunks(_create_sample_chunks())

    # Scoped query for policy_id=10 (chunks 101, 102, 103 belong to policy 10; 104 belongs to policy 99)
    results = temp_vector_store.query_policy_chunks("coverage limit", policy_id=10, top_k=5)
    assert len(results) <= 3
    for r in results:
        assert r.policy_id == 10
        assert r.chunk_id != 104


def test_query_claim_chunks_filtering(temp_vector_store: VectorStore):
    temp_vector_store.upsert_chunks(_create_sample_chunks())

    # Scoped query for claim_id=88
    results = temp_vector_store.query_claim_chunks("collision", claim_id=88, top_k=5)
    assert len(results) == 1
    assert results[0].chunk_id == 104
    assert results[0].claim_id == 88


def test_query_by_document_type(temp_vector_store: VectorStore):
    temp_vector_store.upsert_chunks(_create_sample_chunks())

    # Query only medical_invoice
    results = temp_vector_store.query_by_document_type(
        query_text="hospital charge",
        doc_type="medical_invoice",
        top_k=5,
    )
    assert len(results) == 1
    assert results[0].chunk_id == 103
    assert results[0].document_type == "medical_invoice"


def test_delete_chunk_vector(temp_vector_store: VectorStore):
    temp_vector_store.upsert_chunks(_create_sample_chunks())
    assert temp_vector_store.count() == 4

    temp_vector_store.delete_chunk_vector(chunk_id=101)
    assert temp_vector_store.count() == 3

    results = temp_vector_store.query_similar("Aggregate coverage limit", top_k=5)
    assert not any(r.chunk_id == 101 for r in results)


def test_delete_document_vectors(temp_vector_store: VectorStore):
    temp_vector_store.upsert_chunks(_create_sample_chunks())
    # claim_document_id=1 has chunks 101 and 102
    temp_vector_store.delete_document_vectors(claim_document_id=1)
    assert temp_vector_store.count() == 2

    results = temp_vector_store.query_similar("policy", top_k=5)
    assert not any(r.document_id == 1 for r in results)


def test_delete_policy_vectors(temp_vector_store: VectorStore):
    temp_vector_store.upsert_chunks(_create_sample_chunks())
    # policy_id=99 has chunk 104
    temp_vector_store.delete_policy_vectors(policy_id=99)
    assert temp_vector_store.count() == 3

    results = temp_vector_store.query_similar("Automobile collision", top_k=5)
    assert not any(r.policy_id == 99 for r in results)


def test_delete_claim_vectors(temp_vector_store: VectorStore):
    temp_vector_store.upsert_chunks(_create_sample_chunks())
    # claim_id=20 has chunks 101, 102, 103
    temp_vector_store.delete_claim_vectors(claim_id=20)
    assert temp_vector_store.count() == 1
    assert temp_vector_store.query_similar("collision")[0].chunk_id == 104
