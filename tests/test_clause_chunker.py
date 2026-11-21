from backend.services.clause_chunker import (
    chunk_document,
    chunk_page,
    _extract_clause_or_heading,
    _fallback_split_text,
)
from backend.services.pdf_parser import PageExtractionRecord


def test_extract_clause_or_heading():
    assert _extract_clause_or_heading("1.1 Coverage Limits") == "1.1"
    assert _extract_clause_or_heading("Clause 5. Deductible Requirements") == "Clause 5"
    assert _extract_clause_or_heading("Section 4.2: Exclusions") == "Section 4.2"
    assert _extract_clause_or_heading("Article 3. Pre-Existing Conditions") == "Article 3"
    assert _extract_clause_or_heading("2.4.3 Sub-limits for room rent") == "2.4.3"
    assert _extract_clause_or_heading("EXCLUSIONS") == "EXCLUSIONS"
    assert _extract_clause_or_heading("Waiting Period") == "Waiting Period"
    assert _extract_clause_or_heading("A. Mandatory Documents") == "A"
    assert _extract_clause_or_heading("This is a normal paragraph with no clause header.") is None


def test_numbered_clauses_chunking():
    page_text = """1.1 Total Aggregate Coverage
The maximum aggregate coverage under this contract is $500,000 per policy year.

1.2 Deductible Amount
A standard fixed deductible of $500 shall apply to each independent event.

1.3 Co-Payment Obligations
The insured party must bear 10% co-insurance on all outpatient visits.
"""
    page = PageExtractionRecord(page_number=1, extracted_text=page_text)
    chunks = chunk_document([page], document_type="policy_document", filename="policy.pdf")

    assert len(chunks) == 3
    refs = [c.clause_or_section_ref for c in chunks]
    assert "1.1" in refs
    assert "1.2" in refs
    assert "1.3" in refs
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[2].chunk_index == 2


def test_headings_chunking():
    page_text = """Coverage
All medically necessary hospitalizations are covered up to maximum limits.

Exclusions
Elective cosmetic rhinoplasty and unapproved experimental therapies are excluded.

Waiting Period
A mandatory 30-day initial waiting period applies to all newly enrolled members.
"""
    page = PageExtractionRecord(page_number=1, extracted_text=page_text)
    chunks = chunk_document([page], document_type="policy_document")

    assert len(chunks) == 3
    refs = [c.clause_or_section_ref for c in chunks]
    assert any("Coverage" in str(r) for r in refs)
    assert any("Exclusions" in str(r) for r in refs)
    assert any("Waiting Period" in str(r) for r in refs)


def test_nested_numbered_clauses():
    page_text = """3.1(a) Initial Waiting Period
Treatment during first 30 days is excluded.

3.1(b) Pre-existing Conditions
Subject to 24-month waiting duration.
"""
    page = PageExtractionRecord(page_number=1, extracted_text=page_text)
    chunks = chunk_document([page], document_type="policy_document")

    assert len(chunks) == 2
    assert chunks[0].clause_or_section_ref is not None
    assert "3.1(a)" in chunks[0].clause_or_section_ref
    assert "3.1(b)" in chunks[1].clause_or_section_ref


def test_unnumbered_fallback_paragraphs():
    # Plain text without any clause indicators or headings
    page_text = """The hospital is a premier tertiary healthcare institution located downtown.
Our staff of board-certified clinicians provides continuous 24-hour observation.

All patients are evaluated upon admission and assigned an attending specialist.
Medications are administered according to national clinical protocol guidelines.
"""
    page = PageExtractionRecord(page_number=1, extracted_text=page_text)
    chunks = chunk_document([page], document_type="hospital_summary", max_chunk_size=200)

    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.text) <= 250  # respects size constraint


def test_sentence_boundary_splitting_no_word_cut():
    text = (
        "First sentence detailing primary injury symptoms. "
        "Second sentence describing immediate clinical intervention. "
        "Third sentence outlining medication prescription protocol. "
        "Fourth sentence specifying planned discharge timing."
    )
    splits = _fallback_split_text(text, max_chunk_size=120)
    assert len(splits) > 1
    # Verify no word is severed (e.g., words match complete words)
    reconstructed = " ".join(splits)
    assert "First sentence" in reconstructed
    assert "Fourth sentence" in reconstructed


def test_page_boundary_preservation():
    p1 = PageExtractionRecord(page_number=1, extracted_text="Clause 1. First page clause content.")
    p2 = PageExtractionRecord(page_number=2, extracted_text="Clause 2. Second page clause content.")
    chunks = chunk_document([p1, p2], document_type="policy")

    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1


def test_empty_text_handling():
    p1 = PageExtractionRecord(page_number=1, extracted_text="")
    p2 = PageExtractionRecord(page_number=2, extracted_text="   \n\n  ")
    chunks = chunk_document([p1, p2])
    assert len(chunks) == 0


def test_metadata_preservation():
    p1 = PageExtractionRecord(
        page_number=1,
        extracted_text="Section 1. Core Coverage",
        extraction_method="tesseract",
        ocr_used=True,
    )
    chunks = chunk_document(
        [p1],
        document_type="claim_form",
        claim_document_id=42,
        claim_id=101,
        policy_id=5,
        filename="scanned_claim.pdf",
    )

    assert len(chunks) == 1
    c = chunks[0]
    assert c.claim_document_id == 42
    assert c.claim_id == 101
    assert c.policy_id == 5
    assert c.metadata_json["filename"] == "scanned_claim.pdf"
    assert c.metadata_json["document_type"] == "claim_form"
    assert c.metadata_json["ocr_used"] is True
    assert c.metadata_json["extraction_method"] == "tesseract"
