import io
import os
import shutil
from typing import List, Optional
from pydantic import BaseModel, Field
import pymupdf as fitz
from PIL import Image
import pytesseract
from backend.core.config import get_settings
from backend.core.logging_config import logger


class PageExtractionRecord(BaseModel):
    """Structured extraction record for a single document page."""

    page_number: int = Field(..., ge=1, description="1-based page number")
    extracted_text: str = Field("", description="Extracted text content")
    extraction_method: str = Field("pymupdf", description="pymupdf, pdfplumber, tesseract, direct_text")
    ocr_used: bool = Field(False, description="Whether OCR was executed for this page")
    extraction_status: str = Field("success", description="success, partial, empty, failed")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Extraction or OCR confidence")
    metadata: dict = Field(default_factory=dict, description="Page dimensions, char counts, notes")


class DocumentExtractionResult(BaseModel):
    """Overall result of extracting content from a document file."""

    filename: str
    page_count: int = Field(0, ge=0)
    ocr_applied: bool = Field(False)
    pages: List[PageExtractionRecord] = Field(default_factory=list)
    full_text: str = Field("")
    error_message: Optional[str] = None


def is_tesseract_available() -> bool:
    """Checks whether tesseract binary is accessible and executable."""
    settings = get_settings()
    if settings.tesseract_cmd:
        if os.path.exists(settings.tesseract_cmd) and os.access(settings.tesseract_cmd, os.X_OK):
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
            return True
        return False
    # Check default system PATH
    return shutil.which("tesseract") is not None


def _perform_ocr_on_image(image: Image.Image) -> Optional[str]:
    """Applies Tesseract OCR on a PIL Image with graceful error handling."""
    if not is_tesseract_available():
        return None
    try:
        settings = get_settings()
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        text = pytesseract.image_to_string(image)
        return text.strip() if text else None
    except Exception as e:
        logger.warning(f"OCR execution failed on image: {e}")
        return None


def extract_from_pdf(
    file_bytes: bytes,
    filename: str = "document.pdf",
    min_chars_ocr_threshold: int = 50,
) -> DocumentExtractionResult:
    """Extracts text page-by-page from a PDF using PyMuPDF with Tesseract OCR fallback."""
    pages: List[PageExtractionRecord] = []
    ocr_applied_any = False

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        logger.error(f"Failed to open PDF '{filename}': {e}")
        return DocumentExtractionResult(
            filename=filename,
            page_count=0,
            ocr_applied=False,
            pages=[],
            full_text="",
            error_message=f"Invalid or corrupted PDF file: {str(e)}",
        )

    try:
        page_count = len(doc)
        for page_idx in range(page_count):
            page_num = page_idx + 1
            page = doc[page_idx]

            # 1. Primary extraction via PyMuPDF
            page_text = page.get_text("text").strip()
            method = "pymupdf"
            ocr_used = False
            status = "success" if page_text else "empty"

            # 2. Check if text is sparse or page appears to be a scanned image
            if len(page_text) < min_chars_ocr_threshold:
                # Attempt OCR fallback
                try:
                    pix = page.get_pixmap(dpi=150)
                    pil_img = Image.open(io.BytesIO(pix.tobytes("png")))
                    ocr_text = _perform_ocr_on_image(pil_img)

                    if ocr_text and len(ocr_text) > len(page_text):
                        page_text = ocr_text
                        method = "tesseract"
                        ocr_used = True
                        ocr_applied_any = True
                        status = "success"
                    elif not is_tesseract_available():
                        status = "partial" if page_text else "empty"
                except Exception as ocr_err:
                    logger.warning(f"OCR fallback error on page {page_num} of {filename}: {ocr_err}")
                    status = "partial" if page_text else "failed"

            pages.append(
                PageExtractionRecord(
                    page_number=page_num,
                    extracted_text=page_text,
                    extraction_method=method,
                    ocr_used=ocr_used,
                    extraction_status=status,
                    metadata={
                        "char_count": len(page_text),
                        "width": page.rect.width,
                        "height": page.rect.height,
                    },
                )
            )

        full_text = "\n\n".join([p.extracted_text for p in pages if p.extracted_text]).strip()

        return DocumentExtractionResult(
            filename=filename,
            page_count=page_count,
            ocr_applied=ocr_applied_any,
            pages=pages,
            full_text=full_text,
        )
    finally:
        doc.close()


def extract_from_text(file_bytes: bytes, filename: str = "document.txt") -> DocumentExtractionResult:
    """Extracts content from a plain text document."""
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = file_bytes.decode("latin-1")
        except Exception as e:
            return DocumentExtractionResult(
                filename=filename,
                page_count=0,
                ocr_applied=False,
                pages=[],
                full_text="",
                error_message=f"Could not decode text file: {e}",
            )

    text = text.strip()
    page = PageExtractionRecord(
        page_number=1,
        extracted_text=text,
        extraction_method="direct_text",
        ocr_used=False,
        extraction_status="success" if text else "empty",
        metadata={"char_count": len(text)},
    )
    return DocumentExtractionResult(
        filename=filename,
        page_count=1,
        ocr_applied=False,
        pages=[page],
        full_text=text,
    )


def extract_from_image(file_bytes: bytes, filename: str = "image.png") -> DocumentExtractionResult:
    """Extracts text from a standalone image using Pillow and Tesseract OCR."""
    try:
        image = Image.open(io.BytesIO(file_bytes))
    except Exception as e:
        return DocumentExtractionResult(
            filename=filename,
            page_count=0,
            ocr_applied=False,
            pages=[],
            full_text="",
            error_message=f"Invalid image format: {e}",
        )

    if not is_tesseract_available():
        return DocumentExtractionResult(
            filename=filename,
            page_count=1,
            ocr_applied=False,
            pages=[
                PageExtractionRecord(
                    page_number=1,
                    extracted_text="",
                    extraction_method="tesseract",
                    ocr_used=False,
                    extraction_status="failed",
                    metadata={"error": "Tesseract OCR engine is not installed or available on PATH"},
                )
            ],
            full_text="",
            error_message="Tesseract OCR engine is not installed or available on PATH",
        )

    ocr_text = _perform_ocr_on_image(image) or ""
    page = PageExtractionRecord(
        page_number=1,
        extracted_text=ocr_text,
        extraction_method="tesseract",
        ocr_used=True,
        extraction_status="success" if ocr_text else "empty",
        metadata={"width": image.width, "height": image.height, "char_count": len(ocr_text)},
    )
    return DocumentExtractionResult(
        filename=filename,
        page_count=1,
        ocr_applied=True,
        pages=[page],
        full_text=ocr_text,
    )


def extract_document(
    file_bytes: bytes,
    filename: str,
    min_chars_ocr_threshold: int = 50,
) -> DocumentExtractionResult:
    """Unified entrypoint for extracting text and metadata from supported file formats."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        return extract_from_pdf(
            file_bytes=file_bytes,
            filename=filename,
            min_chars_ocr_threshold=min_chars_ocr_threshold,
        )
    elif ext in ["txt", "log", "csv"]:
        return extract_from_text(file_bytes=file_bytes, filename=filename)
    elif ext in ["png", "jpg", "jpeg", "tiff", "bmp"]:
        return extract_from_image(file_bytes=file_bytes, filename=filename)
    else:
        return DocumentExtractionResult(
            filename=filename,
            page_count=0,
            ocr_applied=False,
            pages=[],
            full_text="",
            error_message=f"Unsupported file format '{ext}'. Allowed: pdf, txt, png, jpg, jpeg, tiff.",
        )
