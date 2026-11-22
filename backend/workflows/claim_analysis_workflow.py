"""ClauseGuard Claim Analysis LangGraph Workflow.

Executes sequential, evidence-grounded claim review:
START -> Evidence Retrieval -> Rule Extraction -> Reviewer -> Analyzer/Calculator -> Recommendation Gate -> Report Persistence -> END
"""

from typing import Any, List, Optional, TypedDict
from langgraph.graph import StateGraph, START, END
from sqlalchemy.orm import Session
from backend.core.logging_config import logger
from backend.models.document_chunk import DocumentChunk
from backend.services.claim_retrieval_service import ClaimRetrievalService, ClaimEvidencePackage
from backend.services.policy_rule_extractor import PolicyRuleExtractor, ExtractedPolicyRule
from backend.services.clause_reviewer import ClauseReviewer, ReviewerSummary
from backend.services.analyzer_calculator import AnalyzerCalculator, AnalysisCalculationResult
from backend.services.recommendation_gate import DeterministicRecommendationGate, RecommendationVerdict
from backend.services.audit_report_service import AuditReportService, ComprehensiveAnalysisReport
from backend.services.llm_provider import BaseLLMProvider, get_llm_provider
from backend.services.vector_store import VectorStore, get_vector_store


class ClaimAnalysisState(TypedDict):
    """Complete, strictly typed execution state for ClauseGuard claim analysis pipeline."""

    claim_id: int
    db: Any  # Session
    llm_provider: Any  # BaseLLMProvider
    vector_store: Any  # VectorStore
    evidence: Optional[ClaimEvidencePackage]
    policy_rules: List[ExtractedPolicyRule]
    reviewer_summary: Optional[ReviewerSummary]
    analysis_result: Optional[AnalysisCalculationResult]
    verdict: Optional[RecommendationVerdict]
    report: Optional[ComprehensiveAnalysisReport]
    db_report_id: Optional[int]
    errors: List[str]
    fallback_used: bool
    fallback_reason: Optional[str]


def retrieval_node(state: ClaimAnalysisState) -> dict:
    """1. Fetches target claim, parent policy, and retrieves isolated evidence packages."""
    logger.info(f"[Workflow Node: 1] Retrieving evidence for Claim {state['claim_id']}")
    try:
        retrieval_svc = ClaimRetrievalService(vector_store=state.get("vector_store"))
        evidence = retrieval_svc.retrieve_claim_evidence(
            db=state["db"],
            claim_id=state["claim_id"],
        )
        return {"evidence": evidence}
    except Exception as e:
        logger.error(f"Retrieval node failed for Claim {state['claim_id']}: {e}")
        return {"errors": state.get("errors", []) + [f"Retrieval error: {str(e)}"]}


def rule_extractor_node(state: ClaimAnalysisState) -> dict:
    """2. Extracts structured, traceable policy rules from retrieved policy chunks."""
    logger.info(f"[Workflow Node: 2] Extracting policy rules for Claim {state['claim_id']}")
    evidence = state.get("evidence")
    if not evidence or not evidence.policy_chunks:
        return {"policy_rules": []}

    try:
        extractor = PolicyRuleExtractor(llm_provider=state.get("llm_provider"))
        # Rehydrate DocumentChunk objects for rule extractor
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
        rules = extractor.extract_rules_from_chunks(chunks)
        return {"policy_rules": rules}
    except Exception as e:
        logger.error(f"Rule extractor node failed: {e}")
        return {"errors": state.get("errors", []) + [f"Rule extraction error: {str(e)}"]}


def reviewer_node(state: ClaimAnalysisState) -> dict:
    """3. Reviewer Gate: Verifies clause applicability before downstream calculations."""
    logger.info(f"[Workflow Node: 3] Reviewer evaluating clause applicability for Claim {state['claim_id']}")
    evidence = state.get("evidence")
    rules = state.get("policy_rules", [])

    if not evidence:
        return {}

    try:
        reviewer = ClauseReviewer()
        reviewer_summary = reviewer.review_rules(rules=rules, evidence=evidence)
        return {"reviewer_summary": reviewer_summary}
    except Exception as e:
        logger.error(f"Reviewer node failed: {e}")
        return {"errors": state.get("errors", []) + [f"Reviewer error: {str(e)}"]}


def analyzer_calculator_node(state: ClaimAnalysisState) -> dict:
    """4. Evaluates fraud signals, policy loopholes, and executes calculations on approved clauses ONLY."""
    logger.info(f"[Workflow Node: 4] Analyzer & Calculator executing for Claim {state['claim_id']}")
    evidence = state.get("evidence")
    reviewer_summary = state.get("reviewer_summary")
    rules = state.get("policy_rules", [])

    if not evidence or not reviewer_summary:
        return {}

    try:
        analyzer = AnalyzerCalculator()
        analysis_res = analyzer.analyze_and_calculate(
            evidence=evidence,
            reviewer_summary=reviewer_summary,
            rules=rules,
        )
        return {"analysis_result": analysis_res}
    except Exception as e:
        logger.error(f"Analyzer/Calculator node failed: {e}")
        return {"errors": state.get("errors", []) + [f"Analyzer error: {str(e)}"]}


def recommendation_gate_node(state: ClaimAnalysisState) -> dict:
    """5. Deterministic 'Should We Take This?' Gate producing advisory verdict."""
    logger.info(f"[Workflow Node: 5] Deterministic Recommendation Gate for Claim {state['claim_id']}")
    analysis_res = state.get("analysis_result")
    reviewer_summary = state.get("reviewer_summary")

    if not analysis_res or not reviewer_summary:
        return {}

    try:
        gate = DeterministicRecommendationGate()
        verdict = gate.evaluate(
            analysis_result=analysis_res,
            reviewer_summary=reviewer_summary,
            fallback_used=state.get("fallback_used", False),
            fallback_reason=state.get("fallback_reason"),
        )
        return {"verdict": verdict}
    except Exception as e:
        logger.error(f"Recommendation gate node failed: {e}")
        return {"errors": state.get("errors", []) + [f"Recommendation gate error: {str(e)}"]}


def report_persistence_node(state: ClaimAnalysisState) -> dict:
    """6. Synthesizes comprehensive analysis report and persists records in SQLite."""
    logger.info(f"[Workflow Node: 6] Persisting Audit Report for Claim {state['claim_id']}")
    evidence = state.get("evidence")
    reviewer_summary = state.get("reviewer_summary")
    analysis_res = state.get("analysis_result")
    verdict = state.get("verdict")
    db = state["db"]

    if not (evidence and reviewer_summary and analysis_res and verdict):
        return {}

    try:
        report_svc = AuditReportService()
        report_data = report_svc.build_report(
            evidence=evidence,
            reviewer_summary=reviewer_summary,
            analysis_result=analysis_res,
            verdict=verdict,
        )
        db_report = report_svc.persist_report(db=db, report_data=report_data)
        return {"report": report_data, "db_report_id": db_report.id}
    except Exception as e:
        logger.error(f"Report persistence node failed: {e}")
        return {"errors": state.get("errors", []) + [f"Report persistence error: {str(e)}"]}


def build_claim_analysis_graph():
    """Compiles the sequential LangGraph workflow."""
    workflow = StateGraph(ClaimAnalysisState)

    workflow.add_node("retrieve_evidence", retrieval_node)
    workflow.add_node("extract_rules", rule_extractor_node)
    workflow.add_node("review_applicability", reviewer_node)
    workflow.add_node("analyze_and_calculate", analyzer_calculator_node)
    workflow.add_node("recommendation_gate", recommendation_gate_node)
    workflow.add_node("generate_and_persist_report", report_persistence_node)

    workflow.add_edge(START, "retrieve_evidence")
    workflow.add_edge("retrieve_evidence", "extract_rules")
    workflow.add_edge("extract_rules", "review_applicability")
    workflow.add_edge("review_applicability", "analyze_and_calculate")
    workflow.add_edge("analyze_and_calculate", "recommendation_gate")
    workflow.add_edge("recommendation_gate", "generate_and_persist_report")
    workflow.add_edge("generate_and_persist_report", END)

    return workflow.compile()


# Global compiled workflow instance
claim_analysis_graph = build_claim_analysis_graph()


def run_claim_analysis(
    claim_id: int,
    db: Session,
    llm_provider: Optional[BaseLLMProvider] = None,
    vector_store: Optional[VectorStore] = None,
) -> ComprehensiveAnalysisReport:
    """High-level runner executing the compiled LangGraph workflow for a claim."""
    provider = llm_provider or get_llm_provider()
    vstore = vector_store or get_vector_store()

    initial_state: ClaimAnalysisState = {
        "claim_id": claim_id,
        "db": db,
        "llm_provider": provider,
        "vector_store": vstore,
        "evidence": None,
        "policy_rules": [],
        "reviewer_summary": None,
        "analysis_result": None,
        "verdict": None,
        "report": None,
        "db_report_id": None,
        "errors": [],
        "fallback_used": False,
        "fallback_reason": None,
    }

    final_state = claim_analysis_graph.invoke(initial_state)

    if final_state.get("errors"):
        logger.error(f"Workflow finished with errors: {final_state['errors']}")

    report = final_state.get("report")
    if not report:
        raise RuntimeError(
            f"Failed to generate analysis report for Claim {claim_id}: {final_state.get('errors')}"
        )

    return report
