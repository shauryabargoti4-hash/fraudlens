from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from backend.api.v1.endpoints.documents import get_vector_store_dep
from backend.main import app
from backend.services.vector_store import VectorSearchResult


def _setup_policy_and_claim(client: TestClient):
    pol_resp = client.post(
        "/api/v1/policies/",
        json={
            "policy_number": "POL-SEARCH-TEST",
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
            "claim_number": "CLM-SEARCH-TEST",
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


def test_search_documents_success(client: TestClient):
    policy_id, claim_id = _setup_policy_and_claim(client)

    mock_vs = MagicMock()
    mock_vs.query_similar.return_value = [
        VectorSearchResult(
            chunk_id=1,
            text="Inpatient hospital room and board capped at $500/day.",
            policy_id=policy_id,
            claim_id=claim_id,
            document_type="policy_document",
            clause_or_section_ref="SEC-2.1",
            page_number=1,
            chunk_index=0,
            similarity_score=0.92,
            distance=0.08,
            metadata={"filename": "policy.pdf"},
        )
    ]

    app.dependency_overrides[get_vector_store_dep] = lambda: mock_vs

    try:
        resp = client.post(
            "/api/v1/documents/search",
            json={
                "query": "room and board sub-limit",
                "top_k": 3,
                "policy_id": policy_id,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "room and board sub-limit"
        assert data["total_results"] == 1
        assert data["results"][0]["chunk_id"] == 1
        assert data["results"][0]["similarity_score"] == 0.92
        assert data["results"][0]["clause_or_section_ref"] == "SEC-2.1"
    finally:
        app.dependency_overrides.pop(get_vector_store_dep, None)


def test_search_documents_empty_query_400(client: TestClient):
    resp = client.post(
        "/api/v1/documents/search",
        json={"query": "   ", "top_k": 5},
    )
    assert resp.status_code == 400
    assert "cannot be empty" in resp.json()["detail"]


def test_search_documents_invalid_top_k(client: TestClient):
    resp = client.post(
        "/api/v1/documents/search",
        json={"query": "room rent", "top_k": 100},  # le=50
    )
    assert resp.status_code == 422


def test_search_documents_nonexistent_policy_404(client: TestClient):
    resp = client.post(
        "/api/v1/documents/search",
        json={"query": "room rent", "policy_id": 999999},
    )
    assert resp.status_code == 404
    assert "Policy with ID 999999 not found" in resp.json()["detail"]


def test_search_documents_nonexistent_claim_404(client: TestClient):
    resp = client.post(
        "/api/v1/documents/search",
        json={"query": "room rent", "claim_id": 999999},
    )
    assert resp.status_code == 404
    assert "Claim with ID 999999 not found" in resp.json()["detail"]


def test_search_documents_compound_filter_construction(client: TestClient):
    policy_id, claim_id = _setup_policy_and_claim(client)

    mock_vs = MagicMock()
    mock_vs.query_similar.return_value = []

    app.dependency_overrides[get_vector_store_dep] = lambda: mock_vs

    try:
        resp = client.post(
            "/api/v1/documents/search",
            json={
                "query": "surgical charges",
                "top_k": 5,
                "policy_id": policy_id,
                "claim_id": claim_id,
                "document_type": "medical_invoice",
            },
        )
        assert resp.status_code == 200
        assert mock_vs.query_similar.called
        kwargs = mock_vs.query_similar.call_args[1]
        assert kwargs["where"] == {
            "$and": [
                {"policy_id": policy_id},
                {"claim_id": claim_id},
                {"document_type": "medical_invoice"},
            ]
        }
    finally:
        app.dependency_overrides.pop(get_vector_store_dep, None)
