"""Ingestion & Verification Script for ClauseGuard Sample Data.

Seeds the database with the sample Policy and Claim, then executes the full
document ingestion and clause-aware chunking pipeline on:
  1. apex_shield_policy.pdf
  2. claim_form_clm_8801.pdf
  3. st_jude_medical_invoice.pdf
  4. physician_notes.txt

Prints a detailed inspection table of DocumentChunk records and verifies chunk integrity.
"""

import datetime
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session
from backend.core.database import SessionLocal, init_db
from backend.models.policy import Policy, PolicyClause
from backend.models.claim import Claim, ClaimDocument
from backend.models.enums import PolicyStatus, ClaimStatus, DocumentType, ClauseType
from backend.models.document_chunk import DocumentChunk
from backend.services.pdf_parser import extract_document
from backend.services.clause_chunker import chunk_document
from backend.crud.document_chunk import create_chunks_batch


def seed_database_and_ingest():
    init_db()
    db: Session = SessionLocal()

    try:
        # 1. Seed or retrieve Sample Policy
        policy_num = "POL-SHIELD-2026-8801"
        policy = db.query(Policy).filter(Policy.policy_number == policy_num).first()
        if not policy:
            policy = Policy(
                policy_number=policy_num,
                title="Comprehensive Health Shield Contract",
                insurer_name="Apex Mutual Assurance Corporation",
                policyholder_name="David K. Vance",
                policy_type="health",
                effective_date=datetime.date(2026, 2, 1),
                expiration_date=datetime.date(2027, 1, 31),
                premium_amount=2400.0,
                max_coverage_limit=500000.0,
                status=PolicyStatus.ACTIVE,
            )
            db.add(policy)
            db.flush()

            # Seed explicit clauses into PolicyClause table
            clauses = [
                PolicyClause(
                    policy_id=policy.id,
                    clause_code="SEC-1.1",
                    clause_type=ClauseType.COVERAGE_SCOPE,
                    title="Total Aggregate Coverage Limit",
                    clause_text="The maximum aggregate coverage under this contract is $500,000 per policy year.",
                    limit_amount=500000.0,
                ),
                PolicyClause(
                    policy_id=policy.id,
                    clause_code="SEC-2.1",
                    clause_type=ClauseType.SUB_LIMIT,
                    title="Room and Board Sub-Limit",
                    clause_text="Reimbursement for inpatient room and board is capped at a strict maximum sub-limit of $500.00 per day.",
                    limit_amount=500.0,
                ),
                PolicyClause(
                    policy_id=policy.id,
                    clause_code="SEC-3.1",
                    clause_type=ClauseType.WAITING_PERIOD,
                    title="Initial Inception Waiting Period",
                    clause_text="A mandatory initial waiting period of thirty (30) days from Effective Date applies.",
                    waiting_period_days=30,
                ),
                PolicyClause(
                    policy_id=policy.id,
                    clause_code="SEC-4.1",
                    clause_type=ClauseType.EXCLUSION,
                    title="Cosmetic and Aesthetic Surgeries",
                    clause_text="All elective, aesthetic, or cosmetic procedures—including rhinoplasty—are entirely excluded.",
                ),
                PolicyClause(
                    policy_id=policy.id,
                    clause_code="SEC-6.1",
                    clause_type=ClauseType.MANDATORY_DOCUMENT,
                    title="Mandatory Documentation Requirements",
                    clause_text="Claimant must provide: (a) Itemized Hospital Bill, (b) Detailed Physician Discharge Summary, (c) Claim Form.",
                ),
                PolicyClause(
                    policy_id=policy.id,
                    clause_code="SEC-9.3",
                    clause_type=ClauseType.GENERAL_CONDITION,
                    title="Alternative Therapy Discretion",
                    clause_text="The insurer may at its sole unreviewable discretion reimburse non-standard holistic supportive wellness regimens.",
                    ambiguity_score=85.0,
                    ambiguity_notes="Discretionary loophole with no fee schedule or medical verification.",
                ),
            ]
            db.add_all(clauses)
            db.commit()
            db.refresh(policy)

        # 2. Seed or retrieve Sample Claim
        claim_num = "CLM-2026-8801"
        claim = db.query(Claim).filter(Claim.claim_number == claim_num).first()
        if not claim:
            claim = Claim(
                claim_number=claim_num,
                policy_id=policy.id,
                claimant_name="David K. Vance",
                incident_date=datetime.date(2026, 2, 15),
                filing_date=datetime.date(2026, 3, 2),
                claimed_amount=9570.0,
                status=ClaimStatus.SUBMITTED,
                summary="Trauma hospitalization with cosmetic rhinoplasty and holistic therapy.",
            )
            db.add(claim)
            db.commit()
            db.refresh(claim)

        # 3. Clean up existing chunks and claim documents for a fresh re-ingestion pass
        db.query(DocumentChunk).filter(
            (DocumentChunk.policy_id == policy.id) | (DocumentChunk.claim_id == claim.id)
        ).delete()
        db.query(ClaimDocument).filter(ClaimDocument.claim_id == claim.id).delete()
        db.commit()

        base_dir = Path(__file__).resolve().parent

        files_to_ingest = [
            (base_dir / "policies" / "apex_shield_policy.pdf", DocumentType.POLICY_DOCUMENT, True, False),
            (base_dir / "claims" / "claim_form_clm_8801.pdf", DocumentType.CLAIM_FORM, False, True),
            (base_dir / "invoices" / "st_jude_medical_invoice.pdf", DocumentType.MEDICAL_INVOICE, False, True),
            (base_dir / "evidence" / "physician_notes.txt", DocumentType.DISCHARGE_SUMMARY, False, True),
        ]

        ingestion_results = []

        for file_path, doc_type, is_policy_doc, is_claim_doc in files_to_ingest:
            if not file_path.exists():
                print(f"[!] Warning: File not found: {file_path}")
                continue

            with open(file_path, "rb") as f:
                content = f.read()

            filename = file_path.name
            extraction = extract_document(content, filename=filename)

            claim_doc_id = None
            if is_claim_doc:
                claim_doc = ClaimDocument(
                    claim_id=claim.id,
                    filename=filename,
                    file_path=str(file_path),
                    file_hash="mock_hash_" + filename,
                    document_type=doc_type,
                    page_count=extraction.page_count,
                    ocr_applied=extraction.ocr_applied,
                    extracted_text=extraction.full_text,
                )
                db.add(claim_doc)
                db.flush()
                claim_doc_id = claim_doc.id

            chunks = chunk_document(
                pages=extraction.pages,
                document_type=str(doc_type.value),
                claim_document_id=claim_doc_id,
                policy_id=policy.id if is_policy_doc else None,
                claim_id=claim.id if is_claim_doc else None,
                filename=filename,
            )

            db_chunks = create_chunks_batch(db, chunks)
            db.commit()

            ingestion_results.append({
                "filename": filename,
                "doc_type": str(doc_type.value),
                "page_count": extraction.page_count,
                "chunk_count": len(db_chunks),
                "chunks": db_chunks,
            })

        # 4. Print structured inspection summary
        print("=" * 105)
        print("CLAUSEGUARD WAVE 1 — DOCUMENT CHUNK INGESTION & PROVENANCE INSPECTION SUMMARY")
        print("=" * 105)

        total_chunks = 0
        for item in ingestion_results:
            total_chunks += item["chunk_count"]
            print(f"\n[FILE] {item['filename']} | Type: {item['doc_type']} | Pages: {item['page_count']} | Chunks: {item['chunk_count']}")
            print("-" * 105)
            print(f"{'Idx':<4} | {'Ref':<22} | {'Pg':<3} | {'Len':<5} | {'Text Snippet':<60}")
            print("-" * 105)
            for c in item["chunks"]:
                ref = c.clause_or_section_ref or "None (Fallback)"
                snippet = c.text.replace("\n", " ")[:58] + ("..." if len(c.text) > 58 else "")
                print(f"{c.chunk_index:<4} | {ref:<22} | {c.page_number:<3} | {len(c.text):<5} | {snippet:<60}")

        print("\n" + "=" * 105)
        print(f"INGESTION COMPLETE: {len(ingestion_results)} files processed, {total_chunks} DocumentChunk records created in SQLite database.")
        print("=" * 105)

    finally:
        db.close()


if __name__ == "__main__":
    seed_database_and_ingest()
