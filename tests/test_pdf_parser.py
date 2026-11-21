import io
from unittest.mock import patch
import pytest
import pymupdf as fitz
from PIL import Image
from backend.services.pdf_parser import (
    extract_from_pdf,
    extract_from_text,
    extract_from_image,
    extract_document,
    PageExtractionRecord,
    DocumentExtractionResult,
)


def _create_test_pdf(pages_text: list[str]) -> bytes:
    """Helper to build a memory PDF with arbitrary page texts."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page(width=500, height=700)
        if text:
            page.insert_text(fitz.Point(50, 50), text, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_pdf_normal_text():
    content = "This is a standard single page insurance policy clause."
    pdf_bytes = _create_test_pdf([content])
    res = extract_from_pdf(pdf_bytes, filename="single.pdf")

    assert res.page_count == 1
    assert len(res.pages) == 1
    assert res.pages[0].page_number == 1
    assert "insurance policy clause" in res.pages[0].extracted_text
    assert res.pages[0].extraction_status == "success"
    assert res.pages[0].ocr_used is False


def test_pdf_multiple_pages_and_page_numbering():
    pages = [
        "Page 1: Scope of cover and general definitions for medical benefits.",
        "Page 2: Exclusions including elective aesthetic surgery and dental care.",
        "Page 3: Claim procedures, submission deadlines and required receipts.",
    ]
    pdf_bytes = _create_test_pdf(pages)
    res = extract_from_pdf(pdf_bytes, filename="multipage.pdf")

    assert res.page_count == 3
    assert len(res.pages) == 3
    for idx, page in enumerate(res.pages):
        assert page.page_number == idx + 1
        assert f"Page {idx + 1}" in page.extracted_text


def test_pdf_empty_page():
    pdf_bytes = _create_test_pdf([""])
    res = extract_from_pdf(pdf_bytes, filename="empty.pdf")

    assert res.page_count == 1
    assert res.pages[0].extracted_text == ""
    assert res.pages[0].extraction_status in ["empty", "partial"]


def test_pdf_scanned_page_ocr_fallback():
    # Page with almost no direct text (< 50 chars threshold)
    sparse_text = "Img"
    pdf_bytes = _create_test_pdf([sparse_text])

    # Mock OCR execution returning recognized text
    with patch("backend.services.pdf_parser._perform_ocr_on_image") as mock_ocr:
        mock_ocr.return_value = "Extracted via OCR: Scanned Hospital Medical Receipt Line Item $500"
        res = extract_from_pdf(pdf_bytes, filename="scanned.pdf", min_chars_ocr_threshold=50)

        assert res.pages[0].ocr_used is True
        assert res.pages[0].extraction_method == "tesseract"
        assert "Scanned Hospital Medical Receipt" in res.pages[0].extracted_text
        assert res.ocr_applied is True


def test_pdf_mixed_text_and_scanned_pages():
    pages = [
        "Page 1: Very long text describing comprehensive coverage and general policy conditions.",
        "X",  # Needs OCR
    ]
    pdf_bytes = _create_test_pdf(pages)

    with patch("backend.services.pdf_parser._perform_ocr_on_image") as mock_ocr:
        mock_ocr.return_value = "Page 2 OCR Scanned Clinical Voucher"
        res = extract_from_pdf(pdf_bytes, filename="mixed.pdf", min_chars_ocr_threshold=50)

        assert res.page_count == 2
        assert res.pages[0].ocr_used is False
        assert res.pages[0].extraction_method == "pymupdf"
        assert res.pages[1].ocr_used is True
        assert res.pages[1].extraction_method == "tesseract"
        assert res.ocr_applied is True


def test_pdf_missing_tesseract_graceful():
    pdf_bytes = _create_test_pdf(["Sparse"])
    with patch("backend.services.pdf_parser.is_tesseract_available", return_value=False):
        res = extract_from_pdf(pdf_bytes, filename="no_tesseract.pdf", min_chars_ocr_threshold=50)
        assert res.page_count == 1
        # Does not crash; records partial extraction
        assert res.pages[0].ocr_used is False
        assert res.pages[0].extraction_status == "partial"


def test_pdf_ocr_failure_does_not_crash():
    pdf_bytes = _create_test_pdf(["Short"])
    with patch("backend.services.pdf_parser._perform_ocr_on_image", side_effect=RuntimeError("OCR crash")):
        res = extract_from_pdf(pdf_bytes, filename="ocr_crash.pdf", min_chars_ocr_threshold=50)
        assert res.page_count == 1
        assert res.pages[0].extraction_status in ["partial", "failed"]


def test_invalid_pdf_handling():
    corrupted_bytes = b"%PDF-corrupted-bytes-12345"
    res = extract_from_pdf(corrupted_bytes, filename="corrupt.pdf")
    assert res.page_count == 0
    assert res.error_message is not None
    assert "Invalid or corrupted PDF" in res.error_message


def test_extract_from_text():
    text_data = "Policy Clause 1.1: General reimbursement guidelines.\nClause 1.2: Deductibles."
    res = extract_from_text(text_data.encode("utf-8"), filename="clause.txt")
    assert res.page_count == 1
    assert "Policy Clause 1.1" in res.full_text
    assert res.pages[0].extraction_method == "direct_text"


def test_extract_from_image_mock_ocr():
    # Create simple image in memory
    img = Image.new("RGB", (200, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    with patch("backend.services.pdf_parser.is_tesseract_available", return_value=True):
        with patch("backend.services.pdf_parser._perform_ocr_on_image", return_value="Itemized Lab Test: $350"):
            res = extract_from_image(img_bytes, filename="receipt.png")
            assert res.page_count == 1
            assert res.ocr_applied is True
            assert "Itemized Lab Test: $350" in res.full_text


def test_unified_extract_document_dispatcher():
    # PDF
    pdf_bytes = _create_test_pdf(["Sample text in PDF"])
    res_pdf = extract_document(pdf_bytes, filename="sample.pdf")
    assert res_pdf.page_count == 1

    # Unsupported format
    res_unknown = extract_document(b"bin", filename="sample.exe")
    assert res_unknown.page_count == 0
    assert "Unsupported file format" in (res_unknown.error_message or "")
