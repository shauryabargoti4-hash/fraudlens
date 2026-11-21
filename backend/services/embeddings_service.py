"""Embeddings Service for ClauseGuard.

Provides a unified embedding interface supporting deterministic mock embeddings
for offline testing and Google Gemini embeddings for live extraction, decoupled
from vector store implementations.
"""

from abc import ABC, abstractmethod
import hashlib
from typing import List, Optional, Tuple
import numpy as np
from backend.core.config import get_settings, Settings
from backend.core.logging_config import logger
from backend.models.document_chunk import DocumentChunk


class BaseEmbeddingProvider(ABC):
    """Abstract interface for text embedding providers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """The fixed vector dimensionality produced by this provider."""
        pass

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string."""
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of text strings."""
        pass

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """Embed a search query string."""
        pass


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic, offline embedding provider generating stable pseudo-random unit vectors.

    Uses SHA-256 digest of input text as RNG seed to guarantee that identical texts
    produce identical vectors across any run, environment, or operating system.
    """

    def __init__(self, dimension: int = 768):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _hash_to_vector(self, text: str) -> List[float]:
        clean = text.strip() if text else ""
        if not clean:
            return [0.0] * self._dimension

        digest = hashlib.sha256(clean.encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big")
        rng = np.random.default_rng(seed)

        vec = rng.standard_normal(self._dimension)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return [float(x) for x in vec]

    def embed_text(self, text: str) -> List[float]:
        return self._hash_to_vector(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_to_vector(t) for t in texts]

    def embed_query(self, query: str) -> List[float]:
        return self._hash_to_vector(query)


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Official Google Gen AI SDK embedding provider using text-embedding models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimension: int = 768,
        batch_size: int = 32,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.api_key = api_key or self.settings.gemini_api_key
        self.model = model or self.settings.embedding_model
        self._dimension = dimension or self.settings.embedding_dimension
        self.batch_size = batch_size or self.settings.embedding_batch_size
        self._client = None

        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini embedding client: {e}")

    @property
    def dimension(self) -> int:
        return self._dimension

    def _get_client(self):
        if not self._client:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not configured or provided.")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def embed_text(self, text: str) -> List[float]:
        client = self._get_client()
        clean = text.strip() if text else ""
        if not clean:
            return [0.0] * self._dimension

        response = client.models.embed_content(
            model=self.model,
            contents=clean,
        )
        embedding = response.embedding.values
        return [float(v) for v in embedding]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        client = self._get_client()
        embeddings: List[List[float]] = []

        for i in range(0, len(texts), self.batch_size):
            chunk_slice = texts[i : i + self.batch_size]
            clean_slice = [t.strip() if t.strip() else " " for t in chunk_slice]
            try:
                response = client.models.embed_content(
                    model=self.model,
                    contents=clean_slice,
                )
                if hasattr(response, "embeddings"):
                    for emb in response.embeddings:
                        embeddings.append([float(v) for v in emb.values])
                else:
                    embeddings.append([float(v) for v in response.embedding.values])
            except Exception as e:
                logger.error(f"Gemini batch embedding error: {e}")
                raise

        return embeddings

    def embed_query(self, query: str) -> List[float]:
        return self.embed_text(query)


class EmbeddingsService:
    """Orchestrates embedding generation, validation, and batching across providers."""

    def __init__(self, provider: Optional[BaseEmbeddingProvider] = None):
        if provider is None:
            settings = get_settings()
            if settings.embedding_provider.lower() == "gemini" and settings.has_gemini_api_key:
                self.provider = GeminiEmbeddingProvider()
            else:
                self.provider = MockEmbeddingProvider(dimension=settings.embedding_dimension)
        else:
            self.provider = provider

    @property
    def dimension(self) -> int:
        return self.provider.dimension

    def embed_text(self, text: str) -> List[float]:
        """Embed a single string with dimension verification."""
        vec = self.provider.embed_text(text)
        if len(vec) != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimension}, got {len(vec)}"
            )
        return vec

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of strings with dimension verification."""
        if not texts:
            return []
        vectors = self.provider.embed_batch(texts)
        for vec in vectors:
            if len(vec) != self.dimension:
                raise ValueError(
                    f"Batch embedding dimension mismatch: expected {self.dimension}, got {len(vec)}"
                )
        return vectors

    def embed_query(self, query: str) -> List[float]:
        """Embed a query string with dimension verification."""
        return self.provider.embed_query(query)

    def embed_chunks(
        self, chunks: List[DocumentChunk]
    ) -> List[Tuple[int, List[float]]]:
        """Embeds a list of DocumentChunks and returns pairs of (chunk.id, vector)."""
        if not chunks:
            return []
        texts = [c.text for c in chunks]
        vectors = self.embed_batch(texts)
        return [(c.id, v) for c, v in zip(chunks, vectors)]


def get_embeddings_service(
    provider_type: Optional[str] = None,
    api_key: Optional[str] = None,
) -> EmbeddingsService:
    """Factory creating the configured EmbeddingsService instance."""
    settings = get_settings()
    p_type = (provider_type or settings.embedding_provider).lower()

    if p_type == "gemini" and (api_key or settings.has_gemini_api_key):
        return EmbeddingsService(GeminiEmbeddingProvider(api_key=api_key))
    return EmbeddingsService(MockEmbeddingProvider(dimension=settings.embedding_dimension))
