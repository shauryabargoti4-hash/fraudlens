"""Debug: show Rule 4.1 source text and ambiguity_flag."""
import sys
sys.path.insert(0, '.')
from backend.core.database import SessionLocal
from backend.services.claim_retrieval_service import ClaimRetrievalService
from backend.services.policy_rule_extractor import PolicyRuleExtractor
from backend.models.document_chunk import DocumentChunk
from backend.services.llm_provider import get_llm_provider
from backend.services.vector_store import get_vector_store

db = SessionLocal()
try:
    retrieval_svc = ClaimRetrievalService(vector_store=get_vector_store())
    evidence = retrieval_svc.retrieve_claim_evidence(db=db, claim_id=1)
    provider = get_llm_provider()
    chunks = [
        DocumentChunk(
            id=c["id"], chunk_index=c["chunk_index"],
            clause_or_section_ref=c["clause_or_section_ref"],
            page_number=c["page_number"], text=c["text"],
        )
        for c in evidence.policy_chunks
    ]
    extractor = PolicyRuleExtractor(llm_provider=provider)
    rules = extractor.extract_rules_from_chunks(chunks)

    print("Rules with ambiguity_flag=True:")
    for r in rules:
        if r.ambiguity_flag:
            print(f"  [{r.rule_type}] {r.clause_reference}")
            print(f"    desc: {r.rule_description}")
            print(f"    source_text_excerpt: {r.source_text_excerpt[:200]}")
            print()

    print("All sub-limit rules:")
    from backend.models.enums import ClauseType
    for r in rules:
        if r.rule_type == ClauseType.SUB_LIMIT:
            print(f"  [{r.clause_reference}] limit={r.limit_amount}")
            print(f"    source: {r.source_text_excerpt[:150]}")
            print()
finally:
    db.close()
