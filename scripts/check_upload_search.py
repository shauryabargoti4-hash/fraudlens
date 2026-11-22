"""Check 5: Upload auto-indexing & filtered search via API."""
import sys
sys.path.insert(0, '.')

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

print("=" * 60)
print("CHECK 5: UPLOAD AUTO-INDEXING & SEARCH ENDPOINT")
print("=" * 60)

# 5a. Upload a new text file and check auto-indexing response
print("\n--- 5a: Upload auto-indexing ---")
test_content = b"""SUPPLEMENTARY MEDICAL REPORT
Patient: David K. Vance
Date: February 20, 2026

Attending physician notes confirm that the patient was admitted on February 15, 2026
following acute lower back pain. Treatment included prescribed physiotherapy sessions
and standard analgesic medication. No surgical intervention was performed for this
specific complaint.

Room allocation: Private ward, 4-day stay.
"""

files = {"file": ("supplementary_report.txt", test_content, "text/plain")}
data = {"policy_id": "1", "claim_id": "1", "document_type": "supporting_evidence"}
resp = client.post("/api/v1/documents/upload", files=files, data=data)
print(f"  Upload status: {resp.status_code}")
if resp.status_code == 200:
    body = resp.json()
    chunks_created = body.get("chunks_created", 0)
    indexed = body.get("indexed_in_vector_store", False)
    idx_error = body.get("indexing_error")
    print(f"  Chunks created: {chunks_created}")
    print(f"  Indexed in vector store: {indexed}")
    if idx_error:
        print(f"  Indexing error (non-fatal): {idx_error}")
    if chunks_created > 0:
        print("  [PASS] Upload created DocumentChunk records")
    else:
        print("  [FAIL] No chunks created")
    if indexed:
        print("  [PASS] Chunks auto-indexed in ChromaDB")
    else:
        print(f"  [WARN] Auto-indexing reported: indexed={indexed}, error={idx_error}")
else:
    print(f"  [FAIL] Upload failed: {resp.text[:300]}")

# 5b. Filtered search — policy_id filter
print("\n--- 5b: Filtered search (policy_id=1, query='waiting period') ---")
search_resp = client.post("/api/v1/documents/search", json={
    "query": "waiting period",
    "policy_id": 1,
    "top_k": 5
})
print(f"  Search status: {search_resp.status_code}")
if search_resp.status_code == 200:
    results = search_resp.json()
    items = results.get("results", [])
    print(f"  Results returned: {len(items)}")
    all_match_policy = all(r.get("policy_id") == 1 for r in items)
    if all_match_policy and len(items) > 0:
        print("  [PASS] All results belong to policy_id=1")
    elif len(items) == 0:
        print("  [WARN] No results returned for 'waiting period' query")
    else:
        mismatches = [r.get("policy_id") for r in items if r.get("policy_id") != 1]
        print(f"  [FAIL] Some results have wrong policy_id: {mismatches}")
    for r in items[:3]:
        snippet = r.get("text", "")[:80]
        print(f"    - [{r.get('document_type')}] {r.get('clause_or_section_ref')}: {snippet}...")
else:
    print(f"  [FAIL] Search failed: {search_resp.text[:300]}")

# 5c. Filtered search — claim_id filter
print("\n--- 5c: Filtered search (claim_id=1, query='rhinoplasty') ---")
search_resp2 = client.post("/api/v1/documents/search", json={
    "query": "rhinoplasty cosmetic",
    "claim_id": 1,
    "top_k": 5
})
print(f"  Search status: {search_resp2.status_code}")
if search_resp2.status_code == 200:
    results2 = search_resp2.json()
    items2 = results2.get("results", [])
    print(f"  Results returned: {len(items2)}")
    all_match_claim = all(r.get("claim_id") == 1 for r in items2)
    if all_match_claim and len(items2) > 0:
        print("  [PASS] All results belong to claim_id=1")
    elif len(items2) == 0:
        print("  [WARN] No results returned for 'rhinoplasty cosmetic' query")
    else:
        print("  [FAIL] Some results have wrong claim_id")
    for r in items2[:3]:
        snippet = r.get("text", "")[:80]
        print(f"    - [{r.get('document_type')}] {snippet}...")
else:
    print(f"  [FAIL] Search failed: {search_resp2.text[:300]}")

# 5d. Combined filter
print("\n--- 5d: Combined filter (policy_id=1, document_type='policy_document') ---")
search_resp3 = client.post("/api/v1/documents/search", json={
    "query": "exclusion cosmetic",
    "policy_id": 1,
    "document_type": "policy_document",
    "top_k": 5
})
print(f"  Search status: {search_resp3.status_code}")
if search_resp3.status_code == 200:
    results3 = search_resp3.json()
    items3 = results3.get("results", [])
    print(f"  Results returned: {len(items3)}")
    all_match = all(
        r.get("policy_id") == 1 and r.get("document_type") == "policy_document"
        for r in items3
    )
    if all_match and len(items3) > 0:
        print("  [PASS] All results match policy_id=1 AND document_type=policy_document")
    elif len(items3) == 0:
        print("  [WARN] No results returned")
    else:
        print("  [FAIL] Filter mismatch in results")
else:
    print(f"  [FAIL] Search failed: {search_resp3.text[:300]}")

# 5e. top_k bounds
print("\n--- 5e: top_k validation ---")
bad_resp = client.post("/api/v1/documents/search", json={
    "query": "test",
    "top_k": 100  # Should be capped or rejected (max 50)
})
print(f"  top_k=100 status: {bad_resp.status_code}")
if bad_resp.status_code == 422:
    print("  [PASS] top_k=100 correctly rejected (validation)")
elif bad_resp.status_code == 200:
    actual_k = len(bad_resp.json().get("results", []))
    print(f"  [INFO] top_k=100 accepted, returned {actual_k} results (server may cap internally)")
