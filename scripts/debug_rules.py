"""Debug: inspect extracted rules and reviewer decisions for Claim 1."""
import sys
sys.path.insert(0, '.')
from backend.core.database import SessionLocal
from backend.services.claim_retrieval_service import ClaimRetrievalService
from backend.services.policy_rule_extractor import PolicyRuleExtractor
from backend.services.clause_reviewer import ClauseReviewer
from backend.models.document_chunk import DocumentChunk
from backend.services.llm_provider import get_llm_provider
from backend.services.vector_store import get_vector_store

db = SessionLocal()
try:
    # 1. Retrieve evidence
    retrieval_svc = ClaimRetrievalService(vector_store=get_vector_store())
    evidence = retrieval_svc.retrieve_claim_evidence(db=db, claim_id=1)
    print(f"Policy chunks: {len(evidence.policy_chunks)}")
    print(f"Invoice chunks: {len(evidence.invoice_chunks)}")
    print(f"Policy effective date: {evidence.policy_effective_date}")
    print(f"Incident date: {evidence.incident_date}")
    print()

    # 2. Extract rules
    provider = get_llm_provider()
    chunks = [
        DocumentChunk(
            id=c["id"],
            chunk_index=c["chunk_index"],
            clause_or_section_ref=c["clause_or_section_ref"],
            page_number=c["page_number"],
            text=c["text"],
        )
        for c in evidence.policy_chunks
    ]
    extractor = PolicyRuleExtractor(llm_provider=provider)
    rules = extractor.extract_rules_from_chunks(chunks)
    print(f"Extracted {len(rules)} rules:")
    for r in rules:
        print(f"  [{r.rule_type}] {r.clause_reference} — {r.rule_description[:80]}")
        if r.limit_amount: print(f"    limit_amount={r.limit_amount}")
        if r.deductible_amount: print(f"    deductible_amount={r.deductible_amount}")
        if r.waiting_period_days: print(f"    waiting_period_days={r.waiting_period_days}")

    print()

    # 3. Reviewer
    reviewer = ClauseReviewer()
    summary = reviewer.review_rules(rules=rules, evidence=evidence)
    print(f"Approved: {len(summary.approved_rules)}, Rejected: {len(summary.rejected_rules)}, "
          f"Uncertain: {len(summary.uncertain_rules)}")
    print()
    print("APPROVED RULES:")
    for a in summary.approved_rules:
        print(f"  [{a.rule_id}] {a.clause_reference} — {a.applicability_reason[:80]}")
    print()
    print("REJECTED RULES:")
    for r in summary.rejected_rules:
        print(f"  [{r.rule_id}] {r.clause_reference} — {r.applicability_reason[:80]}")

    print()
    # 4. What invoice lines are detected?
    print("INVOICE CHUNK TEXT SAMPLES (first 300 chars each):")
    for i, inv in enumerate(evidence.invoice_chunks):
        print(f"  Chunk {inv['id']}: {inv['text'][:300]}")
        print()
finally:
    db.close()
