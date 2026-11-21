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
    chunks: List[DocumentChunkResponse] = Field(default_factory=list)
