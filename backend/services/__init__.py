"""ClauseGuard services package."""

from backend.services.pdf_parser import (
    PageExtractionRecord,
    DocumentExtractionResult,
    extract_from_pdf,
    extract_from_text,
    extract_from_image,
    extract_document,
)
from backend.services.clause_chunker import chunk_document, chunk_page
from backend.services.llm_provider import (
    BaseLLMProvider,
    GeminiLLMProvider,
    MockLLMProvider,
    LLMResponse,
    get_llm_provider,
)
from backend.services.embeddings_service import (
    BaseEmbeddingProvider,
    MockEmbeddingProvider,
    GeminiEmbeddingProvider,
    EmbeddingsService,
    get_embeddings_service,
)
from backend.services.vector_store import (
    VectorStore,
    VectorSearchResult,
    get_vector_store,
)
from backend.services.sync_service import (
    SynchronizationReport,
    synchronize_chunks_to_vector_store,
)

__all__ = [
    "PageExtractionRecord",
    "DocumentExtractionResult",
    "extract_from_pdf",
    "extract_from_text",
    "extract_from_image",
    "extract_document",
    "chunk_document",
    "chunk_page",
    "BaseLLMProvider",
    "GeminiLLMProvider",
    "MockLLMProvider",
    "LLMResponse",
    "get_llm_provider",
    "BaseEmbeddingProvider",
    "MockEmbeddingProvider",
    "GeminiEmbeddingProvider",
    "EmbeddingsService",
    "get_embeddings_service",
    "VectorStore",
    "VectorSearchResult",
    "get_vector_store",
    "SynchronizationReport",
    "synchronize_chunks_to_vector_store",
]
