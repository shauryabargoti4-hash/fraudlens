from fastapi.testclient import TestClient
from backend.services.llm_provider import MockLLMProvider
from backend.api.v1.endpoints.claims import get_llm_provider_dep
from backend.main import app


def _seed_api_claim(client: TestClient) -> tuple[int, int]:
    pol_resp = client.post(
        "/api/v1/policies/",
        json={
            "policy_number": "POL-API-ANALYSIS",
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
            "claim_number": "CLM-API-ANALYSIS",
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


def test_trigger_claim_analysis_endpoint(client: TestClient):
    policy_id, claim_id = _seed_api_claim(client)

    app.dependency_overrides[get_llm_provider_dep] = lambda: MockLLMProvider()

    try:
        resp = client.post(f"/api/v1/claims/{claim_id}/analyze")
        assert resp.status_code == 200
        data = resp.json()

        assert data["claim_id"] == claim_id
        assert data["policy_id"] == policy_id
        assert data["verdict"] in ["TAKE", "REVIEW_REQUIRED", "DO_NOT_TAKE"]
        assert "calculations" in data
        assert "executive_summary" in data
        assert data["overall_risk_score"] >= 0.0

        # Now test fetching the saved analysis report
        get_resp = client.get(f"/api/v1/claims/{claim_id}/analysis")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["claim_id"] == claim_id
        assert get_data["verdict"] == data["verdict"]
        assert get_data["overall_risk_score"] == data["overall_risk_score"]
    finally:
        app.dependency_overrides.pop(get_llm_provider_dep, None)


def test_trigger_claim_analysis_nonexistent_claim_404(client: TestClient):
    resp = client.post("/api/v1/claims/999999/analyze")
    assert resp.status_code == 404
    assert "Claim with ID 999999 not found" in resp.json()["detail"]


def test_get_claim_analysis_nonexistent_claim_404(client: TestClient):
    resp = client.get("/api/v1/claims/999999/analysis")
    assert resp.status_code == 404


def test_get_claim_analysis_no_report_yet_404(client: TestClient):
    policy_id, claim_id = _seed_api_claim(client)
    resp = client.get(f"/api/v1/claims/{claim_id}/analysis")
    assert resp.status_code == 404
    assert f"No analysis report found for Claim {claim_id}" in resp.json()["detail"]
