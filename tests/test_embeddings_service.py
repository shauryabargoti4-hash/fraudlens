import pytest
from unittest.mock import MagicMock, patch
from backend.services.embeddings_service import (
    MockEmbeddingProvider,
    GeminiEmbeddingProvider,
    EmbeddingsService,
    get_embeddings_service,
)
from backend.models.document_chunk import DocumentChunk


def test_mock_embedding_deterministic_vectors():
    provider = MockEmbeddingProvider(dimension=768)
    text = "Section 2.1: Room and board sub-limit is capped at $500 per day."

    vec1 = provider.embed_text(text)
    vec2 = provider.embed_text(text)

    assert len(vec1) == 768
    assert len(vec2) == 768
    assert vec1 == vec2  # Must be strictly identical

    # Different text must produce different vector
    diff_text = "Section 4.1: Cosmetic surgeries are strictly excluded."
    vec_diff = provider.embed_text(diff_text)
    assert vec1 != vec_diff


def test_mock_embedding_batch():
    provider = MockEmbeddingProvider(dimension=128)
    texts = [
        "First policy clause.",
        "Second claim line item.",
        "Third hospital bill charge.",
    ]
    vectors = provider.embed_batch(texts)
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == 128


def test_mock_embedding_empty_text():
    provider = MockEmbeddingProvider(dimension=128)
    vec_empty = provider.embed_text("")
    vec_spaces = provider.embed_text("   \n\t  ")

    assert vec_empty == [0.0] * 128
    assert vec_spaces == [0.0] * 128


def test_embeddings_service_dimension_validation():
    # Mock provider returning unexpected dimension
    bad_provider = MagicMock()
    bad_provider.dimension = 768
    bad_provider.embed_text.return_value = [0.1] * 100  # wrong length!

    service = EmbeddingsService(provider=bad_provider)
    with pytest.raises(ValueError) as exc:
        service.embed_text("Some text")
    assert "dimension mismatch" in str(exc.value)


def test_embeddings_service_embed_chunks():
    provider = MockEmbeddingProvider(dimension=64)
    service = EmbeddingsService(provider=provider)

    chunks = [
        DocumentChunk(id=1, chunk_index=0, text="First chunk clause text.", page_number=1),
        DocumentChunk(id=2, chunk_index=1, text="Second chunk invoice line.", page_number=1),
    ]

    results = service.embed_chunks(chunks)
    assert len(results) == 2
    assert results[0][0] == 1  # chunk.id
    assert len(results[0][1]) == 64  # vector dimension
    assert results[1][0] == 2
    assert len(results[1][1]) == 64


def test_gemini_embedding_provider_mocked():
    provider = GeminiEmbeddingProvider(api_key="test-api-key", dimension=768)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.embedding.values = [0.05] * 768
    mock_client.models.embed_content.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_client):
        vec = provider.embed_text("Test policy text")
        assert len(vec) == 768
        assert vec[0] == 0.05


def test_get_embeddings_service_factory():
    service_mock = get_embeddings_service("mock")
    assert isinstance(service_mock.provider, MockEmbeddingProvider)

    service_gem = get_embeddings_service("gemini", api_key="test-key")
    assert isinstance(service_gem.provider, GeminiEmbeddingProvider)
