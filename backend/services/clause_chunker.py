import re
from typing import List, Optional, Tuple
from backend.services.pdf_parser import PageExtractionRecord
from backend.schemas.document_chunk import DocumentChunkCreate

# Regex patterns for identifying policy clauses and numbered articles
CLAUSE_REGEX = re.compile(
    r"^(?:"
    r"(?:Section|Clause|Article|Part|Item|Line)\s+[0-9A-Za-z\.\-\(\)]+[\.\:\s]*|"  # "Section 4.1", "Clause 5:", "Line 1."
    r"[0-9]+\.[0-9]+(?:\.[0-9]+)*(?:\([a-z0-9]+\))?[\.\:\s]+|"          # "1.1", "2.4.3", "1.1(a)"
    r"[0-9]+\.[\s]+|"                                                    # "1. ", "2. "
    r"(?:[0-9]+)?\([a-z0-9]+\)[\.\:\s]*|"                                # "7(a)", "(b)"
    r"[A-Z]\.[\s]+"                                                      # "A. ", "B. "
    r")",
    re.IGNORECASE,
)

KNOWN_HEADINGS = {
    "coverage",
    "exclusions",
    "exclusion",
    "waiting period",
    "waiting periods",
    "eligibility",
    "claims procedure",
    "claims procedures",
    "required documents",
    "limitations",
    "general conditions",
    "definitions",
    "deductible",
    "deductibles",
    "sub-limits",
    "sub limits",
    "benefits",
    "terms and conditions",
    "scope of cover",
    "policyholder obligations",
    "claim submission",
    "hospitalization expenses",
    "pre-existing conditions",
}


def _extract_clause_or_heading(line: str) -> Optional[str]:
    """Detects whether a line contains a clause identifier or known heading."""
    clean_line = line.strip()
    if not clean_line or len(clean_line) > 120:
        return None

    # Priority 1: Check clause regex match at the start of line
    clause_match = CLAUSE_REGEX.match(clean_line)
    if clause_match:
        # Return matched identifier trimmed of trailing punctuation/space
        raw_ref = clause_match.group(0).strip()
        return raw_ref.rstrip(".: ")

    # Priority 2: Check recognized headings
    lower_line = clean_line.lower().rstrip(".:")
    if lower_line in KNOWN_HEADINGS:
        return clean_line.rstrip(".:")

    # Short title heading detection (all caps or title case, short line)
    if len(clean_line) <= 60 and clean_line.isupper() and any(w.lower() in KNOWN_HEADINGS for w in clean_line.split()):
        return clean_line.rstrip(".:")

    return None


def _fallback_split_text(
    text: str, max_chunk_size: int = 1000, chunk_overlap: int = 150
) -> List[str]:
    """Splits a body of text on paragraph or sentence boundaries without cutting words."""
    text = text.strip()
    if not text:
        return []

    if len(text) <= max_chunk_size:
        return [text]

    chunks: List[str] = []
    # Split primarily by double newline (paragraphs)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    current_chunk = ""
    for para in paragraphs:
        if not current_chunk:
            if len(para) <= max_chunk_size:
                current_chunk = para
            else:
                # Paragraph is too long, split by sentences
                sentences = re.split(r"(?<=[a-zA-Z]{2}[.!?])\s+", para)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    if len(current_chunk) + len(sentence) + 1 <= max_chunk_size:
                        current_chunk = f"{current_chunk} {sentence}".strip()
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        # If single sentence is greater than max_chunk_size, split by words
                        if len(sentence) > max_chunk_size:
                            words = sentence.split()
                            temp = ""
                            for word in words:
                                if len(temp) + len(word) + 1 <= max_chunk_size:
                                    temp = f"{temp} {word}".strip()
                                else:
                                    if temp:
                                        chunks.append(temp)
                                    temp = word
                            current_chunk = temp
                        else:
                            current_chunk = sentence
        elif len(current_chunk) + len(para) + 2 <= max_chunk_size:
            current_chunk = f"{current_chunk}\n\n{para}"
        else:
            chunks.append(current_chunk)
            current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def chunk_page(
    page_text: str,
    page_number: int,
    start_chunk_index: int,
    claim_document_id: Optional[int] = None,
    policy_id: Optional[int] = None,
    claim_id: Optional[int] = None,
    document_type: str = "other",
    filename: str = "",
    extraction_method: str = "pymupdf",
    ocr_used: bool = False,
    max_chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> Tuple[List[DocumentChunkCreate], int]:
    """Segments a single page into structured chunks using clause boundaries, headings, or fallback."""
    if not page_text or not page_text.strip():
        return [], start_chunk_index

    lines = page_text.splitlines()
    segments: List[Tuple[Optional[str], str]] = []  # List of (clause_ref, text)

    current_ref: Optional[str] = None
    current_lines: List[str] = []

    for line in lines:
        detected_ref = _extract_clause_or_heading(line)
        if detected_ref:
            # New clause or heading detected
            if current_lines:
                text_block = "\n".join(current_lines).strip()
                if text_block:
                    segments.append((current_ref, text_block))
            current_ref = detected_ref
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        text_block = "\n".join(current_lines).strip()
        if text_block:
            segments.append((current_ref, text_block))

    # If no clause or heading was detected at all, segment by paragraphs
    if not segments:
        segments = [(None, page_text.strip())]

    chunks: List[DocumentChunkCreate] = []
    chunk_idx = start_chunk_index

    for ref, segment_text in segments:
        # If segment is too long, apply fallback sentence/paragraph splitting
        sub_chunks = _fallback_split_text(segment_text, max_chunk_size=max_chunk_size, chunk_overlap=chunk_overlap)
        for sub_text in sub_chunks:
            if not sub_text.strip():
                continue
            chunk = DocumentChunkCreate(
                claim_document_id=claim_document_id,
                policy_id=policy_id,
                claim_id=claim_id,
                chunk_index=chunk_idx,
                clause_or_section_ref=ref,
                page_number=page_number,
                text=sub_text,
                metadata_json={
                    "document_type": document_type,
                    "filename": filename,
                    "extraction_method": extraction_method,
                    "ocr_used": ocr_used,
                    "char_count": len(sub_text),
                },
            )
            chunks.append(chunk)
            chunk_idx += 1

    return chunks, chunk_idx


def chunk_document(
    pages: List[PageExtractionRecord],
    document_type: str = "other",
    claim_document_id: Optional[int] = None,
    policy_id: Optional[int] = None,
    claim_id: Optional[int] = None,
    filename: str = "",
    max_chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> List[DocumentChunkCreate]:
    """Deterministic clause-aware chunking for an entire multi-page document."""
    all_chunks: List[DocumentChunkCreate] = []
    current_index = 0

    for page in pages:
        page_chunks, next_index = chunk_page(
            page_text=page.extracted_text,
            page_number=page.page_number,
            start_chunk_index=current_index,
            claim_document_id=claim_document_id,
            policy_id=policy_id,
            claim_id=claim_id,
            document_type=document_type,
            filename=filename,
            extraction_method=page.extraction_method,
            ocr_used=page.ocr_used,
            max_chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
        )
        all_chunks.extend(page_chunks)
        current_index = next_index

    return all_chunks
