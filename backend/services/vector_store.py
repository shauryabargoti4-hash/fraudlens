"""ChromaDB Vector Store Integration for ClauseGuard.

Provides persistent vector indexing, metadata-filtered similarity search, and
maintenance operations for DocumentChunk entities.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import chromadb
from chromadb.config import Settings as ChromaSettings
from backend.core.config import get_settings, Settings
from backend.core.logging_config import logger
from backend.models.document_chunk import DocumentChunk
from backend.services.embeddings_service import EmbeddingsService, get_embeddings_service


class VectorSearchResult(BaseModel):
    """Normalized search result retrieved from ChromaDB."""

    chunk_id: int
    text: str
    document_id: Optional[int] = None
    document_type: str = "other"
    policy_id: Optional[int] = None
    claim_id: Optional[int] = None
    clause_or_section_ref: Optional[str] = None
    page_number: int = 1
    chunk_index: int = 0
    distance: Optional[float] = None
    similarity_score: Optional[float] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VectorStore:
    """Manages persistent ChromaDB vector storage, chunk upsert, and metadata-filtered retrieval."""

    def __init__(
        self,
        persist_directory: Optional[Path] = None,
        collection_name: Optional[str] = None,
        embeddings_service: Optional[EmbeddingsService] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.persist_directory = Path(persist_directory or self.settings.chroma_dir).resolve()
        self.collection_name = collection_name or self.settings.chroma_collection_name
        self.embeddings_service = embeddings_service or get_embeddings_service()

        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=ChromaSettings(anonymized_telemetry=False, is_persistent=True),
        )
        self._collection = None

    def get_collection(self) -> chromadb.Collection:
        """Retrieves or creates the target ChromaDB collection."""
        if self._collection is None:
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def _normalize_metadata(self, chunk: DocumentChunk) -> Dict[str, Any]:
        """Normalizes DocumentChunk metadata into ChromaDB-compatible primitive scalar types."""
        meta = {
            "chunk_id": int(chunk.id),
            "claim_document_id": int(chunk.claim_document_id or 0),
            "policy_id": int(chunk.policy_id or 0),
            "claim_id": int(chunk.claim_id or 0),
            "chunk_index": int(chunk.chunk_index),
            "clause_or_section_ref": str(chunk.clause_or_section_ref or ""),
            "page_number": int(chunk.page_number),
            "document_type": str(chunk.metadata_json.get("document_type", "other")),
            "filename": str(chunk.metadata_json.get("filename", "")),
            "char_count": int(len(chunk.text)),
        }
        return meta

    def upsert_chunk(self, chunk: DocumentChunk) -> str:
        """Index or update a single DocumentChunk vector."""
        vec_id = f"chunk_{chunk.id}"
        embedding = self.embeddings_service.embed_text(chunk.text)
        metadata = self._normalize_metadata(chunk)

        collection = self.get_collection()
        collection.upsert(
            ids=[vec_id],
            embeddings=[embedding],
            documents=[chunk.text],
            metadatas=[metadata],
        )
        return vec_id

    def upsert_chunks(self, chunks: List[DocumentChunk]) -> int:
        """Index or update a batch of DocumentChunks in ChromaDB."""
        if not chunks:
            return 0

        ids = [f"chunk_{c.id}" for c in chunks]
        texts = [c.text for c in chunks]
        metadatas = [self._normalize_metadata(c) for c in chunks]
        embeddings = self.embeddings_service.embed_batch(texts)

        collection = self.get_collection()
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        logger.info(f"Successfully upserted {len(chunks)} chunks into ChromaDB '{self.collection_name}'")
        return len(chunks)

    def count(self) -> int:
        """Total number of vectors in the collection."""
        return self.get_collection().count()

    def query_similar(
        self,
        query_text: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[VectorSearchResult]:
        """Perform semantic similarity search with optional metadata filtering."""
        collection = self.get_collection()
        total_items = collection.count()
        if total_items == 0:
            return []

        actual_k = min(top_k, total_items)
        query_vec = self.embeddings_service.embed_query(query_text)

        query_kwargs = {
            "query_embeddings": [query_vec],
            "n_results": actual_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where

        try:
            results = collection.query(**query_kwargs)
        except Exception as e:
            logger.error(f"ChromaDB query failed with filter {where}: {e}")
            return []

        search_results: List[VectorSearchResult] = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return []

        ids = results["ids"][0]
        docs = results["documents"][0] if results.get("documents") else [""] * len(ids)
        metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)
        distances = results["distances"][0] if results.get("distances") else [0.0] * len(ids)

        for chunk_vec_id, doc_text, meta, dist in zip(ids, docs, metas, distances):
            chunk_id_int = meta.get("chunk_id")
            if chunk_id_int is None:
                try:
                    chunk_id_int = int(chunk_vec_id.replace("chunk_", ""))
                except Exception:
                    chunk_id_int = 0

            # Cosine distance to similarity score: similarity = 1 - distance
            # (Bounded to 0.0 - 1.0)
            similarity = max(0.0, min(1.0, 1.0 - (dist if dist is not None else 0.0)))

            search_results.append(
                VectorSearchResult(
                    chunk_id=chunk_id_int,
                    text=doc_text,
                    document_id=meta.get("claim_document_id") if meta.get("claim_document_id") != 0 else None,
                    document_type=meta.get("document_type", "other"),
                    policy_id=meta.get("policy_id") if meta.get("policy_id") != 0 else None,
                    claim_id=meta.get("claim_id") if meta.get("claim_id") != 0 else None,
                    clause_or_section_ref=meta.get("clause_or_section_ref") or None,
                    page_number=meta.get("page_number", 1),
                    chunk_index=meta.get("chunk_index", 0),
                    distance=dist,
                    similarity_score=similarity,
                    metadata=meta,
                )
            )

        return search_results

    def query_policy_chunks(
        self, query_text: str, policy_id: int, top_k: int = 5
    ) -> List[VectorSearchResult]:
        """Scoped search retrieving relevant policy clauses for a specific policy."""
        return self.query_similar(
            query_text=query_text,
            top_k=top_k,
            where={"policy_id": int(policy_id)},
        )

    def query_claim_chunks(
        self, query_text: str, claim_id: int, top_k: int = 5
    ) -> List[VectorSearchResult]:
        """Scoped search retrieving relevant chunks for a specific claim."""
        return self.query_similar(
            query_text=query_text,
            top_k=top_k,
            where={"claim_id": int(claim_id)},
        )

    def query_by_document_type(
        self,
        query_text: str,
        doc_type: str,
        policy_id: Optional[int] = None,
        claim_id: Optional[int] = None,
        top_k: int = 5,
    ) -> List[VectorSearchResult]:
        """Retrieve chunks filtered by document_type and optional policy/claim scope."""
        filter_conditions = [{"document_type": {"$eq": doc_type}}]
        if policy_id is not None:
            filter_conditions.append({"policy_id": {"$eq": int(policy_id)}})
        if claim_id is not None:
            filter_conditions.append({"claim_id": {"$eq": int(claim_id)}})

        where = {"$and": filter_conditions} if len(filter_conditions) > 1 else filter_conditions[0]
        return self.query_similar(query_text=query_text, top_k=top_k, where=where)

    def delete_chunk_vector(self, chunk_id: int) -> None:
        """Deletes a vector corresponding to a specific DocumentChunk ID."""
        vec_id = f"chunk_{chunk_id}"
        collection = self.get_collection()
        collection.delete(ids=[vec_id])

    def delete_document_vectors(self, claim_document_id: int) -> None:
        """Deletes all vectors belonging to a specific claim document."""
        collection = self.get_collection()
        collection.delete(where={"claim_document_id": int(claim_document_id)})

    def delete_policy_vectors(self, policy_id: int) -> None:
        """Deletes all vectors belonging to a policy."""
        collection = self.get_collection()
        collection.delete(where={"policy_id": int(policy_id)})

    def delete_claim_vectors(self, claim_id: int) -> None:
        """Deletes all vectors belonging to a claim."""
        collection = self.get_collection()
        collection.delete(where={"claim_id": int(claim_id)})

    def reset_collection(self) -> None:
        """Deletes and re-creates the collection for testing/maintenance."""
        try:
            self._client.delete_collection(name=self.collection_name)
        except Exception:
            pass
        self._collection = None
        self.get_collection()


def get_vector_store(
    persist_directory: Optional[Path] = None,
    collection_name: Optional[str] = None,
    embeddings_service: Optional[EmbeddingsService] = None,
) -> VectorStore:
    """Factory creating configured VectorStore instance."""
    return VectorStore(
        persist_directory=persist_directory,
        collection_name=collection_name,
        embeddings_service=embeddings_service,
    )
