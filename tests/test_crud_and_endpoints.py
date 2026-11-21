from fastapi.testclient import TestClient


def test_policy_full_lifecycle(client: TestClient):
    # 1. Create Policy
    policy_payload = {
        "policy_number": "POL-LIFE-001",
        "title": "Corporate Health Elite",
        "insurer_name": "Apex Assurance",
        "policyholder_name": "Acme Corp",
        "policy_type": "health",
        "effective_date": "2026-01-01",
        "expiration_date": "2027-01-01",
        "premium_amount": 25000.0,
        "max_coverage_limit": 1000000.0,
        "status": "active",
        "clauses": [
            {
                "clause_code": "EXCL-A1",
                "clause_type": "exclusion",
                "title": "Experimental Treatments",
                "clause_text": "Non-FDA approved experimental therapies are not covered.",
                "ambiguity_score": 10.0,
            }
        ],
    }

    create_resp = client.post("/api/v1/policies/", json=policy_payload)
    assert create_resp.status_code == 201
    policy_data = create_resp.json()
    policy_id = policy_data["id"]
    assert policy_data["policy_number"] == "POL-LIFE-001"
    assert len(policy_data["clauses"]) == 1

    # 2. Prevent duplicate policy_number
    dup_resp = client.post("/api/v1/policies/", json=policy_payload)
    assert dup_resp.status_code == 409

    # 3. Get Policy by ID
    get_resp = client.get(f"/api/v1/policies/{policy_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == policy_id

    # 4. Add Another Clause
    clause_payload = {
        "clause_code": "SUB-D1",
        "clause_type": "sub_limit",
        "title": "Dental Emergency Limit",
        "clause_text": "Dental emergencies are subject to a 2,000 max limit per year.",
        "limit_amount": 2000.0,
        "ambiguity_score": 5.0,
    }
    add_clause_resp = client.post(f"/api/v1/policies/{policy_id}/clauses", json=clause_payload)
    assert add_clause_resp.status_code == 201
    assert add_clause_resp.json()["clause_code"] == "SUB-D1"

    # 5. List Policies
    list_resp = client.get("/api/v1/policies/?page=1&page_size=10")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    assert len(list_data["items"]) >= 1

    # 6. Update Policy
    update_payload = {"title": "Corporate Health Elite Plus"}
    update_resp = client.put(f"/api/v1/policies/{policy_id}", json=update_payload)
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Corporate Health Elite Plus"


def test_claim_full_lifecycle(client: TestClient):
    # Setup prerequisite policy
    pol_resp = client.post(
        "/api/v1/policies/",
        json={
            "policy_number": "POL-FOR-CLAIM-01",
            "title": "Travel Shield",
            "insurer_name": "Apex Travel Insure",
            "policyholder_name": "Michael Scott",
            "policy_type": "travel",
            "effective_date": "2026-05-01",
            "expiration_date": "2026-06-01",
            "premium_amount": 150.0,
            "max_coverage_limit": 50000.0,
        },
    )
    policy_id = pol_resp.json()["id"]

    # 1. Create Claim
    claim_payload = {
        "claim_number": "CLM-TRV-999",
        "policy_id": policy_id,
        "claimant_name": "Michael Scott",
        "incident_date": "2026-05-10",
        "filing_date": "2026-05-12",
        "claimed_amount": 3200.0,
        "status": "submitted",
    }
    claim_resp = client.post("/api/v1/claims/", json=claim_payload)
    assert claim_resp.status_code == 201
    claim_data = claim_resp.json()
    claim_id = claim_data["id"]
    assert claim_data["claim_number"] == "CLM-TRV-999"

    # 2. Attach Document
    doc_payload = {
        "filename": "clinic_bill.pdf",
        "file_path": "/storage/uploads/clinic_bill.pdf",
        "file_hash": "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
        "document_type": "medical_invoice",
        "page_count": 2,
    }
    doc_resp = client.post(f"/api/v1/claims/{claim_id}/documents", json=doc_payload)
    assert doc_resp.status_code == 201
    assert doc_resp.json()["filename"] == "clinic_bill.pdf"

    # 3. Add Discrepancy Finding
    finding_payload = {
        "claim_id": claim_id,
        "finding_type": "amount_inflation",
        "severity": "medium",
        "title": "Hospital charges exceed standard room tariff",
        "description": "Room rate charged ($1,200/night) exceeds standard contracted rate ($800/night).",
        "policy_reference": "Section 4.1 Room Rent",
        "suggested_action": "Request itemized daily hospital ledger",
    }
    finding_resp = client.post(f"/api/v1/claims/{claim_id}/findings", json=finding_payload)
    assert finding_resp.status_code == 201
    assert finding_resp.json()["title"] == finding_payload["title"]

    # 4. Fetch Claim and check relations
    get_claim_resp = client.get(f"/api/v1/claims/{claim_id}")
    assert get_claim_resp.status_code == 200
    fetched_claim = get_claim_resp.json()
    assert len(fetched_claim["documents"]) == 1
    assert fetched_claim["documents"][0]["filename"] == "clinic_bill.pdf"

    # 5. Delete Claim
    del_resp = client.delete(f"/api/v1/claims/{claim_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"

    # 6. Verify 404
    assert client.get(f"/api/v1/claims/{claim_id}").status_code == 404
