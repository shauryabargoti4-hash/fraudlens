import hashlib
import os
import re
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from backend.core.config import get_settings, Settings
from backend.core.database import get_db
from backend.core.logging_config import logger
from backend.crud.claim import get_claim as crud_get_claim
from backend.crud.policy import get_policy as crud_get_policy
from backend.crud.document_chunk import (
    create_chunks_batch,
    get_chunks_by_document,
    get_chunks_by_policy,
    get_chunks_by_claim,
)
from backend.models.claim import ClaimDocument
from backend.models.enums import DocumentType
from backend.schemas.document_chunk import (
    DocumentChunkListResponse,
    DocumentChunkResponse,
    DocumentUploadResponse,
    DocumentSearchRequest,
    DocumentSearchResultItem,
    DocumentSearchResponse,
)
from backend.services.clause_chunker import chunk_document
from backend.services.pdf_parser import extract_document
from backend.services.vector_store import VectorStore, get_vector_store

router = APIRouter()


def get_vector_store_dep() -> VectorStore:
    """Dependency provider for ChromaDB vector store."""
    return get_vector_store()


def sanitize_filename(filename: str) -> str:
    """Sanitizes filename against path traversal and unsafe characters."""
    base = os.path.basename(filename)
    # Strip null bytes, slashes, control chars
    clean = re.sub(r"[^\w\.\-\_]", "_", base)
    return clean or "document"


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and chunk document (PDF, TXT, Image)",
)
async def upload_document(
    file: UploadFile = File(..., description="Document file to upload (PDF, TXT, PNG, JPG, JPEG)"),
    document_type: DocumentType = Form(DocumentType.OTHER, description="Category of document"),
    policy_id: Optional[int] = Form(None, description="Optional associated Policy ID"),
    claim_id: Optional[int] = Form(None, description="Optional associated Claim ID"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    vector_store: VectorStore = Depends(get_vector_store_dep),
) -> DocumentUploadResponse:
    """Multipart upload pipeline: validates file, stores securely, extracts text/OCR, chunks content, and persists."""
    # 1. Require at least one association
    if policy_id is None and claim_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded document must be associated with either a 'policy_id' or a 'claim_id'.",
        )

    # 2. Verify associations exist in database
    if policy_id is not None:
        policy = crud_get_policy(db, policy_id=policy_id)
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Policy with ID {policy_id} not found.",
            )

    if claim_id is not None:
        claim = crud_get_claim(db, claim_id=claim_id)
        if not claim:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim with ID {claim_id} not found.",
            )

    # 3. Filename & Extension validation
    raw_filename = file.filename or "uploaded_file"
    clean_name = sanitize_filename(raw_filename)
    extension = clean_name.lower().rsplit(".", 1)[-1] if "." in clean_name else ""

    if extension not in settings.allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{extension}' is not supported. Allowed: {settings.allowed_extensions}",
        )

    # 4. Stream & Size validation
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum permissible limit of {settings.max_upload_size_mb} MB.",
        )

    # 5. Compute SHA256 hash and unique storage path
    file_hash = hashlib.sha256(content).hexdigest()
    unique_prefix = uuid.uuid4().hex[:12]
    saved_filename = f"{unique_prefix}_{clean_name}"
    settings.ensure_directories()
    saved_path = settings.upload_dir / saved_filename

    # Save to disk
    try:
        with open(saved_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to persist uploaded file to '{saved_path}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write document to storage.",
        )

    claim_doc_id: Optional[int] = None

    try:
        # 6. Extract text & metadata via parsing pipeline
        extraction_res = extract_document(file_bytes=content, filename=clean_name)
        if extraction_res.error_message and not extraction_res.pages:
            # Fatal extraction error (e.g., corrupt PDF)
            raise ValueError(extraction_res.error_message)

        # 7. Create or update document record
        if claim_id is not None:
            claim_doc = ClaimDocument(
                claim_id=claim_id,
                filename=clean_name,
                file_path=str(saved_path),
                file_hash=file_hash,
                document_type=document_type,
                page_count=extraction_res.page_count,
                ocr_applied=extraction_res.ocr_applied,
                extracted_text=extraction_res.full_text,
                extracted_metadata={
                    "page_count": extraction_res.page_count,
                    "pages": [p.model_dump() for p in extraction_res.pages],
                },
            )
            db.add(claim_doc)
            db.flush()
            claim_doc_id = claim_doc.id

        if policy_id is not None and claim_id is None:
            policy = crud_get_policy(db, policy_id=policy_id)
            if policy:
                policy.document_path = str(saved_path)
                policy.raw_text = extraction_res.full_text

        # 8. Clause-Aware Chunking
        chunk_dtos = chunk_document(
            pages=extraction_res.pages,
            document_type=str(document_type.value if hasattr(document_type, "value") else document_type),
            claim_document_id=claim_doc_id,
            policy_id=policy_id,
            claim_id=claim_id,
            filename=clean_name,
        )

        # 9. Persist Chunks
        db_chunks = create_chunks_batch(db, chunks_in=chunk_dtos)
        db.commit()

        # 10. Automatically index chunks in ChromaDB Vector Store
        indexed_in_vector_store = True
        indexing_error = None
        try:
            vector_store.upsert_chunks(db_chunks)
            logger.info(
                f"Successfully auto-indexed {len(db_chunks)} chunks for '{clean_name}' into ChromaDB"
            )
        except Exception as vs_err:
            indexed_in_vector_store = False
            indexing_error = str(vs_err)
            logger.error(f"Failed to auto-index chunks in ChromaDB for '{clean_name}': {vs_err}")

        logger.info(
            f"Successfully ingested '{clean_name}': {extraction_res.page_count} pages, "
            f"{len(db_chunks)} chunks, OCR={extraction_res.ocr_applied}, indexed={indexed_in_vector_store}"
        )

        return DocumentUploadResponse(
            status="success",
            message="Document uploaded, extracted, and chunked successfully.",
            claim_document_id=claim_doc_id,
            policy_id=policy_id,
            claim_id=claim_id,
            filename=clean_name,
            file_path=str(saved_path),
            file_hash=file_hash,
            page_count=extraction_res.page_count,
            ocr_applied=extraction_res.ocr_applied,
            total_chunks=len(db_chunks),
            indexed_in_vector_store=indexed_in_vector_store,
            indexing_error=indexing_error,
            chunks=[DocumentChunkResponse.model_validate(c) for c in db_chunks],
        )

    except ValueError as val_err:
        db.rollback()
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Document parsing error: {str(val_err)}",
        )
    except Exception as exc:
        db.rollback()
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        logger.exception(f"Unhandled error processing document '{clean_name}': {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing document: {str(exc)}",
        )


@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunkListResponse,
    summary="Get all chunks for a claim document",
)
def get_document_chunks(document_id: int, db: Session = Depends(get_db)) -> DocumentChunkListResponse:
    """Retrieve all chunks belonging to a specific claim document, ordered by chunk index."""
    chunks = get_chunks_by_document(db, claim_document_id=document_id)
    return DocumentChunkListResponse(
        document_id=document_id,
        total_chunks=len(chunks),
        chunks=[DocumentChunkResponse.model_validate(c) for c in chunks],
    )


@router.get(
    "/policy/{policy_id}/chunks",
    response_model=DocumentChunkListResponse,
    summary="Get all chunks for a policy",
)
def get_policy_chunks(policy_id: int, db: Session = Depends(get_db)) -> DocumentChunkListResponse:
    """Retrieve all chunks belonging to a policy, ordered by chunk index."""
    chunks = get_chunks_by_policy(db, policy_id=policy_id)
    return DocumentChunkListResponse(
        policy_id=policy_id,
        total_chunks=len(chunks),
        chunks=[DocumentChunkResponse.model_validate(c) for c in chunks],
    )


@router.get(
    "/claim/{claim_id}/chunks",
    response_model=DocumentChunkListResponse,
    summary="Get all chunks for a claim",
)
def get_claim_chunks(claim_id: int, db: Session = Depends(get_db)) -> DocumentChunkListResponse:
    """Retrieve all chunks belonging to a claim across all attached documents."""
    chunks = get_chunks_by_claim(db, claim_id=claim_id)
    return DocumentChunkListResponse(
        claim_id=claim_id,
        total_chunks=len(chunks),
        chunks=[DocumentChunkResponse.model_validate(c) for c in chunks],
    )


@router.post(
    "/search",
    response_model=DocumentSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Semantic document chunk search with metadata filters",
)
def search_documents(
    search_req: DocumentSearchRequest,
    db: Session = Depends(get_db),
    vector_store: VectorStore = Depends(get_vector_store_dep),
) -> DocumentSearchResponse:
    """Semantic vector search across document chunks with optional policy_id, claim_id, and document_type filters."""
    query_clean = search_req.query.strip()
    if not query_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty or whitespace only.",
        )

    # Validate policy and claim existence if filters are provided
    if search_req.policy_id is not None:
        policy = crud_get_policy(db, policy_id=search_req.policy_id)
        if not policy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Policy with ID {search_req.policy_id} not found.",
            )

    if search_req.claim_id is not None:
        claim = crud_get_claim(db, claim_id=search_req.claim_id)
        if not claim:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Claim with ID {search_req.claim_id} not found.",
            )

    # Construct metadata filters
    filter_conditions = []
    if search_req.policy_id is not None:
        filter_conditions.append({"policy_id": int(search_req.policy_id)})
    if search_req.claim_id is not None:
        filter_conditions.append({"claim_id": int(search_req.claim_id)})
    if search_req.document_type is not None and search_req.document_type.strip():
        filter_conditions.append({"document_type": search_req.document_type.strip()})

    where_filter = None
    if len(filter_conditions) == 1:
        where_filter = filter_conditions[0]
    elif len(filter_conditions) > 1:
        where_filter = {"$and": filter_conditions}

    try:
        raw_results = vector_store.query_similar(
            query_text=query_clean,
            top_k=search_req.top_k,
            where=where_filter,
        )
    except Exception as e:
        logger.error(f"Vector search failed for query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while executing vector search.",
        )

    items = [
        DocumentSearchResultItem(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            text=r.text,
            policy_id=r.policy_id,
            claim_id=r.claim_id,
            document_type=r.document_type,
            clause_or_section_ref=r.clause_or_section_ref,
            page_number=r.page_number,
            chunk_index=r.chunk_index,
            similarity_score=r.similarity_score,
            distance=r.distance,
            metadata=r.metadata,
        )
        for r in raw_results
    ]

    return DocumentSearchResponse(
        query=query_clean,
        total_results=len(items),
        results=items,
    )
