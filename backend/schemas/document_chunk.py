import datetime
from typing import List, Optional
from pydantic import Field
from backend.schemas.common import BaseSchema, TimestampedSchema


class DocumentChunkBase(BaseSchema):
    chunk_index: int = Field(..., ge=0, description="0-based index of chunk within the document")
    clause_or_section_ref: Optional[str] = Field(None, max_length=100, description="Clause code or section heading reference")
    page_number: int = Field(1, ge=1, description="1-based source page number")
    text: str = Field(..., min_length=1, description="Original extracted chunk text")
    metadata_json: dict = Field(default_factory=dict, description="Metadata dictionary including extraction source and coordinates")


class DocumentChunkCreate(DocumentChunkBase):
    claim_document_id: Optional[int] = None
    policy_id: Optional[int] = None
    claim_id: Optional[int] = None


class DocumentChunkResponse(DocumentChunkBase):
    id: int
    claim_document_id: Optional[int] = None
    policy_id: Optional[int] = None
    claim_id: Optional[int] = None
    created_at: datetime.datetime


class DocumentChunkListResponse(BaseSchema):
    document_id: Optional[int] = None
    policy_id: Optional[int] = None
    claim_id: Optional[int] = None
    total_chunks: int
    chunks: List[DocumentChunkResponse]


class DocumentUploadResponse(BaseSchema):
    status: str = "success"
    message: str = "Document uploaded, extracted, and chunked successfully."
    claim_document_id: Optional[int] = None
    policy_id: Optional[int] = None
    claim_id: Optional[int] = None
    filename: str
    file_path: str
    file_hash: str
    page_count: int
    ocr_applied: bool
    total_chunks: int
    indexed_in_vector_store: bool = Field(True, description="Whether chunks were successfully upserted into ChromaDB")
    indexing_error: Optional[str] = Field(None, description="Error message if vector indexing failed")
    chunks: List[DocumentChunkResponse] = Field(default_factory=list)


class DocumentSearchRequest(BaseSchema):
    """Query and filter payload for semantic chunk retrieval."""

    query: str = Field(..., min_length=1, description="Semantic search query string")
    top_k: int = Field(5, ge=1, le=50, description="Maximum number of chunks to return")
    policy_id: Optional[int] = Field(None, description="Optional policy ID filter")
    claim_id: Optional[int] = Field(None, description="Optional claim ID filter")
    document_type: Optional[str] = Field(None, description="Optional document type filter")


class DocumentSearchResultItem(BaseSchema):
    """Normalized search result returned by semantic search endpoint."""

    chunk_id: int
    document_id: Optional[int] = None
    text: str
    policy_id: Optional[int] = None
    claim_id: Optional[int] = None
    document_type: str = "other"
    clause_or_section_ref: Optional[str] = None
    page_number: int = 1
    chunk_index: int = 0
    similarity_score: Optional[float] = None
    distance: Optional[float] = None
    metadata: dict = Field(default_factory=dict)


class DocumentSearchResponse(BaseSchema):
    """Response containing retrieved semantic chunks and search metadata."""

    query: str
    total_results: int
    results: List[DocumentSearchResultItem] = Field(default_factory=list)
