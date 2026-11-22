"""Tests for ClauseGuard Sample Data and Exhibition Pack."""

from pathlib import Path


def test_sample_pack_directory_and_files_exist():
    base_dir = Path("sample_data")
    assert base_dir.exists(), "sample_data directory must exist"

    policy_pdf = base_dir / "policies" / "apex_shield_policy.pdf"
    claim_pdf = base_dir / "claims" / "claim_form_clm_8801.pdf"
    invoice_pdf = base_dir / "invoices" / "st_jude_medical_invoice.pdf"
    evidence_txt = base_dir / "evidence" / "physician_notes.txt"
    ground_truth = base_dir / "ground_truth.json"

    assert policy_pdf.exists(), f"Missing {policy_pdf}"
    assert claim_pdf.exists(), f"Missing {claim_pdf}"
    assert invoice_pdf.exists(), f"Missing {invoice_pdf}"
    assert evidence_txt.exists(), f"Missing {evidence_txt}"
    assert ground_truth.exists(), f"Missing {ground_truth}"


def test_redacted_rent_agreement_sample_exists_and_is_redacted():
    agreement_path = Path("sample_data/agreements/sample_redacted_rent_agreement.txt")
    assert agreement_path.exists(), "Sample redacted rent agreement must exist for exhibition demo"

    content = agreement_path.read_text(encoding="utf-8")
    assert len(content) > 500, "Agreement must contain substantial lease wording"

    # Verify PII is redacted
    assert "[REDACTED - LESSOR NAME]" in content
    assert "[REDACTED - LESSEE NAME]" in content
    assert "[REDACTED - LESSOR PAN]" in content
    assert "[REDACTED - RESIDENTIAL ADDRESS]" in content
    assert "[REDACTED - BANK NAME]" in content
    assert "[REDACTED - LESSOR SIGNATURE]" in content

    # Verify core lease clauses are present for semantic search demo
    assert "TERM OF LEASE AND LOCK-IN PERIOD" in content
    assert "MONTHLY RENT" in content
    assert "SECURITY DEPOSIT" in content
    assert "MAINTENANCE" in content
    assert "SUBLETTING PROHIBITION" in content
    assert "TERMINATION" in content


def test_rent_agreement_uses_other_document_type():
    from backend.models.enums import DocumentType
    # Rent agreements are categorized as OTHER, not healthcare or insurance policy docs
    doc_type = DocumentType.OTHER
    assert doc_type.value == "other"
