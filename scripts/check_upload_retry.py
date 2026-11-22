"""Check 5a retry: Upload with correct document_type."""
import sys
sys.path.insert(0, '.')

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

print("=" * 60)
print("CHECK 5a: UPLOAD AUTO-INDEXING (corrected document_type)")
print("=" * 60)

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
data = {"policy_id": "1", "claim_id": "1", "document_type": "other"}
resp = client.post("/api/v1/documents/upload", files=files, data=data)
print(f"  Upload status: {resp.status_code}")
if resp.status_code == 200:
    body = resp.json()
    chunks = body.get("chunks_created", 0)
    indexed = body.get("indexed_in_vector_store", False)
    idx_err = body.get("indexing_error")
    print(f"  Chunks created: {chunks}")
    print(f"  Indexed in vector store: {indexed}")
    if idx_err:
        print(f"  Indexing error (non-fatal): {idx_err}")
    if chunks > 0:
        print("  [PASS] Upload created DocumentChunk records")
    else:
        print("  [FAIL] No chunks created")
    if indexed:
        print("  [PASS] Chunks auto-indexed in ChromaDB on upload")
    else:
        print(f"  [WARN] Auto-indexing: indexed={indexed}, error={idx_err}")
elif resp.status_code == 422:
    print(f"  [FAIL] Validation error: {resp.json()}")
else:
    print(f"  [FAIL] Upload failed ({resp.status_code}): {resp.text[:300]}")
