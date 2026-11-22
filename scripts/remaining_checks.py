"""Complete remaining Wave 3 verification checks (1-6)."""
import sys, inspect
sys.path.insert(0, '.')

from backend.core.database import SessionLocal
from backend.workflows.claim_analysis_workflow import run_claim_analysis
from backend.models.report import AnalysisReport, AuditLog
from backend.models.finding import DiscrepancyFinding
from backend.models.enums import AdvisoryVerdict
from fastapi.testclient import TestClient
from backend.main import app
from collections import Counter

db = SessionLocal()
client = TestClient(app)
all_results = []

def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    all_results.append((name, passed))
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)

try:
    # =========================================================
    print("=" * 60)
    print("CHECK 1: IDEMPOTENCY")
    print("=" * 60)

    reports_before = db.query(AnalysisReport).filter(AnalysisReport.claim_id == 1).count()
    findings_before = db.query(DiscrepancyFinding).filter(DiscrepancyFinding.claim_id == 1).count()
    audits_before = db.query(AuditLog).filter(AuditLog.entity_type == "claim", AuditLog.entity_id == "1").count()
    print(f"  Before: {reports_before} reports, {findings_before} findings, {audits_before} audit logs")

    report = run_claim_analysis(claim_id=1, db=db)

    reports_after = db.query(AnalysisReport).filter(AnalysisReport.claim_id == 1).count()
    findings_after = db.query(DiscrepancyFinding).filter(DiscrepancyFinding.claim_id == 1).count()
    audits_after = db.query(AuditLog).filter(AuditLog.entity_type == "claim", AuditLog.entity_id == "1").count()
    print(f"  After:  {reports_after} reports, {findings_after} findings, {audits_after} audit logs")

    new_reports = reports_after - reports_before
    new_findings = findings_after - findings_before
    new_audits = audits_after - audits_before
    print(f"  Delta: +{new_reports} reports, +{new_findings} findings, +{new_audits} audit logs")

    record("1 new report per run (no within-run duplication)", new_reports == 1, f"got {new_reports}")
    record("Re-run verdict consistent", report.verdict == AdvisoryVerdict.DO_NOT_TAKE, str(report.verdict))
    record("New findings created for new report", new_findings >= 1, f"+{new_findings}")
    record("New audit log entries created", new_audits >= 1, f"+{new_audits}")

    # =========================================================
    print()
    print("=" * 60)
    print("CHECK 2: REVIEWER-BEFORE-CALCULATOR GATE ORDER")
    print("=" * 60)

    from backend.workflows.claim_analysis_workflow import claim_analysis_graph
    nodes = list(claim_analysis_graph.nodes.keys())
    rev_idx = nodes.index("review_applicability") if "review_applicability" in nodes else -1
    calc_idx = nodes.index("analyze_and_calculate") if "analyze_and_calculate" in nodes else -1
    record("Reviewer before Calculator in LangGraph", rev_idx >= 0 and calc_idx >= 0 and rev_idx < calc_idx,
           f"positions: reviewer={rev_idx}, calculator={calc_idx}")

    from backend.services.analyzer_calculator import AnalyzerCalculator
    calc_source = inspect.getsource(AnalyzerCalculator._execute_calculations)
    record("Calculator gates on approved_rule_ids", "approved_rule_ids" in calc_source)

    # =========================================================
    print()
    print("=" * 60)
    print("CHECK 3: HALLUCINATION TRAPS")
    print("=" * 60)

    from backend.services.clause_reviewer import ClauseReviewer
    reviewer_src = inspect.getsource(ClauseReviewer._assess_single_rule)

    record("Silence-as-absence protection documented", "Silence-as-absence" in reviewer_src)

    tail = reviewer_src.split("Default fallback")[-1] if "Default fallback" in reviewer_src else reviewer_src[-300:]
    record("Default fallback returns APPROVED (not REJECTED)", "outcome=ReviewerOutcome.APPROVED" in tail)

    record("Cross-clause contamination guard (reviewer)", "is_room_rule" in reviewer_src and "source_lower" in reviewer_src)

    record("Cross-clause contamination guard (calculator)", "src_lower" in calc_source or "source_text_excerpt" in calc_source)

    # Verify EXCLUSION is checked BEFORE ambiguity gate
    excl_pos = reviewer_src.find("EXCLUSION rules")
    ambig_pos = reviewer_src.find("Check for ambiguity")
    record("Exclusion check runs before ambiguity gate",
           excl_pos >= 0 and ambig_pos >= 0 and excl_pos < ambig_pos,
           f"exclusion@{excl_pos}, ambiguity@{ambig_pos}")

    # =========================================================
    print()
    print("=" * 60)
    print("CHECK 4: FALLBACK DISCLOSURE")
    print("=" * 60)

    from backend.services.llm_provider import get_llm_provider
    provider = get_llm_provider()
    print(f"  Active LLM Provider: {type(provider).__name__}")

    record("Report carries fallback_used", hasattr(report, "fallback_used"), f"={report.fallback_used}")
    record("Report carries fallback_reason", hasattr(report, "fallback_reason"), f"={report.fallback_reason}")

    from backend.services.recommendation_gate import DeterministicRecommendationGate
    gate_src = inspect.getsource(DeterministicRecommendationGate.evaluate)
    record("Gate: fallback_used → REVIEW_REQUIRED", "fallback_used" in gate_src and "REVIEW_REQUIRED" in gate_src)

    # =========================================================
    print()
    print("=" * 60)
    print("CHECK 5: UPLOAD AUTO-INDEXING & SEARCH ENDPOINT")
    print("=" * 60)

    # 5a. Upload
    test_content = b"SUPPLEMENTARY NOTE\nPatient David Vance admitted Feb 15 2026.\nRoom: private ward, 4-day stay.\n"
    files = {"file": ("supp_note.txt", test_content, "text/plain")}
    data = {"policy_id": "1", "claim_id": "1", "document_type": "other"}
    resp = client.post("/api/v1/documents/upload", files=files, data=data)
    upload_ok = resp.status_code in (200, 201)
    if upload_ok:
        body = resp.json()
        chunks = body.get("total_chunks", 0)
        indexed = body.get("indexed_in_vector_store", False)
        idx_err = body.get("indexing_error")
        record("Upload creates chunks", chunks > 0, f"{chunks} chunks")
        record("Upload auto-indexes in ChromaDB", indexed is True, f"indexed={indexed}, error={idx_err}")
    else:
        record("Upload succeeds", False, f"status={resp.status_code}: {resp.text[:200]}")

    # 5b. Filtered search — policy_id
    sr = client.post("/api/v1/documents/search", json={"query": "waiting period", "policy_id": 1, "top_k": 5})
    if sr.status_code == 200:
        items = sr.json().get("results", [])
        all_match = all(r.get("policy_id") == 1 for r in items) and len(items) > 0
        record("Search filter: policy_id=1", all_match, f"{len(items)} results")
    else:
        record("Search filter: policy_id=1", False, f"status={sr.status_code}")

    # 5c. Filtered search — claim_id
    sr2 = client.post("/api/v1/documents/search", json={"query": "rhinoplasty", "claim_id": 1, "top_k": 5})
    if sr2.status_code == 200:
        items2 = sr2.json().get("results", [])
        all_match2 = all(r.get("claim_id") == 1 for r in items2) and len(items2) > 0
        record("Search filter: claim_id=1", all_match2, f"{len(items2)} results")
    else:
        record("Search filter: claim_id=1", False, f"status={sr2.status_code}")

    # 5d. Combined filter
    sr3 = client.post("/api/v1/documents/search", json={
        "query": "exclusion cosmetic", "policy_id": 1, "document_type": "policy_document", "top_k": 5
    })
    if sr3.status_code == 200:
        items3 = sr3.json().get("results", [])
        all_match3 = all(r.get("policy_id") == 1 and r.get("document_type") == "policy_document" for r in items3)
        record("Search combined filter", all_match3 and len(items3) > 0, f"{len(items3)} results")
    else:
        record("Search combined filter", False, f"status={sr3.status_code}")

    # 5e. top_k bounds
    sr4 = client.post("/api/v1/documents/search", json={"query": "test", "top_k": 100})
    record("top_k=100 rejected (validation)", sr4.status_code == 422)

    # =========================================================
    print()
    print("=" * 60)
    print("CHECK 6: CONFIG & SECRETS HYGIENE")
    print("=" * 60)

    import os
    # Check .env for hardcoded API keys
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            env_content = f.read()
        has_real_key = any(
            line.strip().startswith("GEMINI_API_KEY=") and len(line.split("=", 1)[1].strip()) > 10
            and not line.split("=", 1)[1].strip().startswith("your_")
            and not line.split("=", 1)[1].strip().startswith("${")
            and not line.split("=", 1)[1].strip().startswith("\"your_")
            for line in env_content.splitlines()
            if not line.strip().startswith("#")
        )
        record(".env: no hardcoded real API key", not has_real_key)
    else:
        print("  [INFO] No .env file found (OK for Docker/CI)")
        record(".env: no hardcoded real API key", True, "no .env file")

    # Check config.py for hardcoded paths or keys
    config_path = os.path.join(os.getcwd(), "backend", "core", "config.py")
    if os.path.exists(config_path):
        with open(config_path) as f:
            config_content = f.read()
        has_abs_path = "C:\\" in config_content or "/home/" in config_content or "/Users/" in config_content
        record("config.py: no absolute paths", not has_abs_path)

        has_hardcoded_key = "AIza" in config_content or "sk-" in config_content
        record("config.py: no hardcoded API keys", not has_hardcoded_key)
    else:
        record("config.py exists", False, "not found")

    # Check DATABASE_URL is portable
    from backend.core.config import get_settings
    settings = get_settings()
    db_url = str(settings.database_url)
    record("DATABASE_URL is relative/portable", "C:\\" not in db_url and "/home/" not in db_url, db_url[:80])

    # =========================================================
    print()
    print("=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, p in all_results if p)
    failed = sum(1 for _, p in all_results if not p)
    print(f"  {passed} PASSED, {failed} FAILED out of {len(all_results)} checks")
    if failed == 0:
        print("  ALL REMAINING VERIFICATION CHECKS PASSED ✓")
    else:
        print("  FAILURES:")
        for name, p in all_results:
            if not p:
                print(f"    ✗ {name}")

finally:
    db.close()
