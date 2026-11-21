import io
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import pymupdf as fitz
from PIL import Image


def _create_simple_pdf_bytes(text: str = "Clause 1. Standard Policy Agreement.") -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=500, height=700)
    page.insert_text(fitz.Point(50, 50), text, fontsize=11)
    b = doc.tobytes()
    doc.close()
    return b


def _setup_policy_and_claim(client: TestClient):
    pol_resp = client.post(
        "/api/v1/policies/",
        json={
            "policy_number": "POL-UPLOAD-TEST",
            "title": "Hospital Shield Plan",
            "insurer_name": "Apex Assurance",
            "policyholder_name": "David Vance",
            "policy_type": "health",
            "effective_date": "2026-02-01",
            "expiration_date": "2027-02-01",
            "max_coverage_limit": 500000.0,
        },
    )
    assert pol_resp.status_code == 201
    policy_id = pol_resp.json()["id"]

    claim_resp = client.post(
        "/api/v1/claims/",
        json={
            "claim_number": "CLM-UPLOAD-TEST",
            "policy_id": policy_id,
            "claimant_name": "David Vance",
            "incident_date": "2026-02-15",
            "filing_date": "2026-03-02",
            "claimed_amount": 9570.0,
        },
    )
    assert claim_resp.status_code == 201
    claim_id = claim_resp.json()["id"]

    return policy_id, claim_id


def test_valid_pdf_upload_associated_with_claim(client: TestClient, tmp_path: Path):
    policy_id, claim_id = _setup_policy_and_claim(client)
    pdf_bytes = _create_simple_pdf_bytes(
        "1.1 Medical Reimbursement Scope.\n"
        "All inpatient hospital expenses are subject to policy conditions.\n\n"
        "1.2 Specific Deductibles.\n"
        "A $500 deductible applies per admission."
    )

    with patch("backend.core.config.get_settings") as mock_settings:
        from backend.core.config import get_settings
        current = get_settings()
        mock_settings.return_value = current
        current.upload_dir = tmp_path / "uploads"
        current.upload_dir.mkdir(parents=True, exist_ok=True)

        files = {"file": ("claim_invoice.pdf", pdf_bytes, "application/pdf")}
        data = {
            "document_type": "medical_invoice",
            "claim_id": str(claim_id),
            "policy_id": str(policy_id),
        }

        resp = client.post("/api/v1/documents/upload", files=files, data=data)
        assert resp.status_code == 201
        res_data = resp.json()
        assert res_data["status"] == "success"
        assert res_data["filename"] == "claim_invoice.pdf"
        assert res_data["page_count"] == 1
        assert res_data["total_chunks"] >= 2
        claim_doc_id = res_data["claim_document_id"]
        assert claim_doc_id is not None

        # Verify chunks query
        chunk_resp = client.get(f"/api/v1/documents/{claim_doc_id}/chunks")
        assert chunk_resp.status_code == 200
        assert chunk_resp.json()["total_chunks"] == res_data["total_chunks"]


def test_valid_txt_upload_associated_with_policy(client: TestClient, tmp_path: Path):
    policy_id, _ = _setup_policy_and_claim(client)
    txt_content = (
        "Section 1. Core Coverage Terms\n"
        "Emergency hospital treatments are covered up to policy max limit.\n\n"
        "Section 2. Waiting Period\n"
        "30-day initial waiting period applies."
    ).encode("utf-8")

    files = {"file": ("policy_terms.txt", txt_content, "text/plain")}
    data = {
        "document_type": "policy_document",
        "policy_id": str(policy_id),
    }

    resp = client.post("/api/v1/documents/upload", files=files, data=data)
    assert resp.status_code == 201
    res_data = resp.json()
    assert res_data["total_chunks"] >= 2
    assert res_data["policy_id"] == policy_id

    # Verify policy chunks query
    pol_chunk_resp = client.get(f"/api/v1/documents/policy/{policy_id}/chunks")
    assert pol_chunk_resp.status_code == 200
    assert pol_chunk_resp.json()["total_chunks"] >= 2


def test_valid_image_upload_mock_ocr(client: TestClient):
    _, claim_id = _setup_policy_and_claim(client)

    img = Image.new("RGB", (300, 150), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    with patch("backend.services.pdf_parser.is_tesseract_available", return_value=True):
        with patch("backend.services.pdf_parser._perform_ocr_on_image", return_value="Pharmacy Bill: $250"):
            files = {"file": ("receipt.png", img_bytes, "image/png")}
            data = {"document_type": "medical_invoice", "claim_id": str(claim_id)}
            resp = client.post("/api/v1/documents/upload", files=files, data=data)
            assert resp.status_code == 201
            res_data = resp.json()
            assert res_data["ocr_applied"] is True
            assert res_data["total_chunks"] >= 1


def test_missing_associations_rejected(client: TestClient):
    pdf_bytes = _create_simple_pdf_bytes("Test")
    files = {"file": ("doc.pdf", pdf_bytes, "application/pdf")}
    # Neither policy_id nor claim_id
    resp = client.post("/api/v1/documents/upload", files=files, data={})
    assert resp.status_code == 400
    assert "must be associated with either" in resp.json()["detail"]


def test_nonexistent_policy_or_claim_404(client: TestClient):
    pdf_bytes = _create_simple_pdf_bytes("Test")
    files = {"file": ("doc.pdf", pdf_bytes, "application/pdf")}

    resp_pol = client.post("/api/v1/documents/upload", files=files, data={"policy_id": "99999"})
    assert resp_pol.status_code == 404

    resp_clm = client.post("/api/v1/documents/upload", files=files, data={"claim_id": "99999"})
    assert resp_clm.status_code == 404


def test_unsupported_file_extension(client: TestClient):
    _, claim_id = _setup_policy_and_claim(client)
    files = {"file": ("script.sh", b"echo hello", "text/x-sh")}
    resp = client.post(
        "/api/v1/documents/upload",
        files=files,
        data={"claim_id": str(claim_id)},
    )
    assert resp.status_code == 400
    assert "not supported" in resp.json()["detail"]


def test_empty_file_rejected(client: TestClient):
    _, claim_id = _setup_policy_and_claim(client)
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    resp = client.post(
        "/api/v1/documents/upload",
        files=files,
        data={"claim_id": str(claim_id)},
    )
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"]


def test_invalid_corrupted_pdf_422(client: TestClient):
    _, claim_id = _setup_policy_and_claim(client)
    files = {"file": ("bad.pdf", b"%PDF-corrupted-data-header", "application/pdf")}
    resp = client.post(
        "/api/v1/documents/upload",
        files=files,
        data={"claim_id": str(claim_id)},
    )
    assert resp.status_code == 422
    assert "parsing error" in resp.json()["detail"]


def test_filename_sanitization(client: TestClient):
    _, claim_id = _setup_policy_and_claim(client)
    pdf_bytes = _create_simple_pdf_bytes("Clean text.")
    # Path traversal attempt in filename
    files = {"file": ("../../etc/passwd.pdf", pdf_bytes, "application/pdf")}
    resp = client.post(
        "/api/v1/documents/upload",
        files=files,
        data={"claim_id": str(claim_id)},
    )
    assert resp.status_code == 201
    clean_filename = resp.json()["filename"]
    assert "/" not in clean_filename
    assert "\\" not in clean_filename
    assert "passwd.pdf" in clean_filename


def test_file_size_limit_413(client: TestClient):
    _, claim_id = _setup_policy_and_claim(client)
    from backend.core.config import get_settings, Settings
    from backend.main import app

    current_settings = get_settings()
    # Create copy with tiny size limit for testing
    test_settings = Settings(
        max_upload_size_mb=0.0001,  # ~100 bytes
        allowed_extensions=current_settings.allowed_extensions,
        upload_dir=current_settings.upload_dir,
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        large_bytes = b"X" * 250
        files = {"file": ("big.pdf", large_bytes, "application/pdf")}
        resp = client.post(
            "/api/v1/documents/upload",
            files=files,
            data={"claim_id": str(claim_id)},
        )
        assert resp.status_code == 413
        assert "exceeds maximum permissible limit" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_upload_real_generated_sample_policy_and_claim_files(client: TestClient):
    policy_id, claim_id = _setup_policy_and_claim(client)

    base_dir = Path(__file__).resolve().parent.parent / "sample_data"
    policy_pdf_path = base_dir / "policies" / "apex_shield_policy.pdf"
    invoice_pdf_path = base_dir / "invoices" / "st_jude_medical_invoice.pdf"

    assert policy_pdf_path.exists()
    assert invoice_pdf_path.exists()

    # 1. Upload sample policy
    with open(policy_pdf_path, "rb") as f:
        pol_bytes = f.read()

    resp_pol = client.post(
        "/api/v1/documents/upload",
        files={"file": ("apex_shield_policy.pdf", pol_bytes, "application/pdf")},
        data={"document_type": "policy_document", "policy_id": str(policy_id)},
    )
    assert resp_pol.status_code == 201
    pol_data = resp_pol.json()
    assert pol_data["page_count"] == 2
    assert pol_data["total_chunks"] >= 6
    # Verify clause detection on policy chunks
    clause_refs = [c["clause_or_section_ref"] for c in pol_data["chunks"] if c.get("clause_or_section_ref")]
    assert any("1.1" in r for r in clause_refs)
    assert any("2.1" in r for r in clause_refs)
    assert any("4.1" in r for r in clause_refs)

    # 2. Upload sample invoice attached to claim
    with open(invoice_pdf_path, "rb") as f:
        inv_bytes = f.read()

    resp_inv = client.post(
        "/api/v1/documents/upload",
        files={"file": ("st_jude_medical_invoice.pdf", inv_bytes, "application/pdf")},
        data={"document_type": "medical_invoice", "claim_id": str(claim_id)},
    )
    assert resp_inv.status_code == 201
    inv_data = resp_inv.json()
    assert inv_data["page_count"] == 1
    assert inv_data["total_chunks"] >= 1
    assert any("Private Patient Room" in c["text"] for c in inv_data["chunks"])
