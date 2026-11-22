from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pymupdf as fitz
from backend.api.v1.endpoints.documents import get_vector_store_dep
from backend.main import app


def _create_simple_pdf_bytes(text: str = "Section 1.1 Inpatient coverage terms.") -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=500, height=700)
    page.insert_text(fitz.Point(50, 50), text, fontsize=11)
    b = doc.tobytes()
    doc.close()
    return b


def _setup_policy(client: TestClient) -> int:
    pol_resp = client.post(
        "/api/v1/policies/",
        json={
            "policy_number": "POL-AUTO-INDEX-TEST",
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
    return pol_resp.json()["id"]


def test_upload_auto_indexes_chunks_into_vector_store(client: TestClient):
    policy_id = _setup_policy(client)

    mock_vector_store = MagicMock()
    mock_vector_store.upsert_chunks.return_value = 1

    app.dependency_overrides[get_vector_store_dep] = lambda: mock_vector_store

    try:
        pdf_bytes = _create_simple_pdf_bytes("Section 1.1: Standard coverage clause.")
        files = {"file": ("policy.pdf", pdf_bytes, "application/pdf")}
        data = {"document_type": "policy_document", "policy_id": str(policy_id)}

        resp = client.post("/api/v1/documents/upload", files=files, data=data)
        assert resp.status_code == 201
        res_data = resp.json()

        assert res_data["status"] == "success"
        assert res_data["total_chunks"] >= 1
        assert res_data["indexed_in_vector_store"] is True
        assert res_data["indexing_error"] is None

        # Verify upsert_chunks was called with the persisted chunks
        assert mock_vector_store.upsert_chunks.called
        chunks_passed = mock_vector_store.upsert_chunks.call_args[0][0]
        assert len(chunks_passed) == res_data["total_chunks"]
        assert chunks_passed[0].id is not None
    finally:
        app.dependency_overrides.pop(get_vector_store_dep, None)


def test_upload_graceful_handling_when_vector_store_fails(client: TestClient):
    policy_id = _setup_policy(client)

    mock_vector_store = MagicMock()
    mock_vector_store.upsert_chunks.side_effect = RuntimeError("Chroma connection timeout")

    app.dependency_overrides[get_vector_store_dep] = lambda: mock_vector_store

    try:
        pdf_bytes = _create_simple_pdf_bytes("Section 2.1: Exclusions and waiting periods.")
        files = {"file": ("policy.pdf", pdf_bytes, "application/pdf")}
        data = {"document_type": "policy_document", "policy_id": str(policy_id)}

        resp = client.post("/api/v1/documents/upload", files=files, data=data)
        # Upload must still succeed (201) because SQLite is authoritative
        assert resp.status_code == 201
        res_data = resp.json()

        assert res_data["status"] == "success"
        assert res_data["total_chunks"] >= 1
        assert res_data["indexed_in_vector_store"] is False
        assert "Chroma connection timeout" in res_data["indexing_error"]

        # Ensure chunks were still saved to SQLite and can be retrieved
        doc_chunks_resp = client.get(f"/api/v1/documents/policy/{policy_id}/chunks")
        assert doc_chunks_resp.status_code == 200
        assert doc_chunks_resp.json()["total_chunks"] >= 1
    finally:
        app.dependency_overrides.pop(get_vector_store_dep, None)
