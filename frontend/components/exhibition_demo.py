"""Exhibition Demo Component for ClauseGuard."""

import os
from pathlib import Path
import streamlit as st
from frontend.api_client import ClauseGuardAPIClient, APIClientError


def render_exhibition_demo(api_client: ClauseGuardAPIClient):
    """Renders reliable, dual-mode exhibition demonstration for live presentations."""
    st.subheader("🎪 Exhibition & Conference Live Demonstration")
    st.markdown(
        """
        Welcome to the ClauseGuard live interactive exhibition interface.
        Select from two independent demonstration workflows:
        """
    )

    demo_mode = st.radio(
        "Select Exhibition Workflow",
        options=[
            "🏥 Scenario 1: Health Insurance Claim Audit (Apex Mutual CLM-2026-8801)",
            "🏠 Scenario 2: Redacted Residential Rent Agreement (Lease Contract Clause Retrieval)",
        ],
        index=0,
    )

    st.markdown("<hr style='margin: 12px 0 20px 0; border-color: #E2E8F0;'/>", unsafe_allow_html=True)

    # ==========================================================================
    # SCENARIO 1: INSURANCE CLAIM AUDIT
    # ==========================================================================
    if "Scenario 1" in demo_mode:
        st.markdown("### 🏥 Health Insurance Claim Auditing Flow")
        st.markdown(
            """
            This demonstration runs the full **LangGraph Sequential Pipeline** on our built-in benchmark claim:
            **Apex Mutual Assurance vs. David K. Vance (Claim $9,570.00)**.
            """
        )

        c1, c2 = st.columns([1, 2])
        with c1:
            run_btn = st.button("▶️ Run End-to-End Analysis", type="primary", use_container_width=True)

        if run_btn:
            with st.spinner("Executing LangGraph nodes (Retrieval → Extraction → Reviewer → Calculator → Gate)..."):
                try:
                    res = api_client.trigger_claim_analysis(1)
                    st.session_state["active_report"] = res
                    st.session_state["active_claim_id"] = 1
                    st.success("Analysis executed successfully! View full audit report below.")
                except Exception as e:
                    st.error(f"Analysis failed: {e}")

        if "active_report" in st.session_state and st.session_state.get("active_claim_id") == 1:
            from frontend.components.report_view import render_report_view
            render_report_view(st.session_state["active_report"])

    # ==========================================================================
    # SCENARIO 2: REDACTED RENT AGREEMENT
    # ==========================================================================
    else:
        st.markdown("### 🏠 Redacted Residential Rent Agreement Flow")
        st.info(
            """
            ⚖️ **Scope & Legal Disclaimer**:
            ClauseGuard is an explainable document intelligence and clause-retrieval engine.
            While health insurance claims run through a dedicated medical fraud rules engine,
            this demonstration showcases **cross-document clause extraction and semantic retrieval**
            on legal lease contracts. It does not fabricate insurance fraud verdicts or provide legal advice.
            """,
            icon="ℹ️",
        )

        # Locate sample agreement file
        sample_path = Path("sample_data/agreements/sample_redacted_rent_agreement.txt")
        if not sample_path.exists():
            # Try project-relative path
            sample_path = Path(__file__).resolve().parent.parent.parent / "sample_data" / "agreements" / "sample_redacted_rent_agreement.txt"

        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown("#### 1. Inspect Redacted Lease Agreement")
            if sample_path.exists():
                with open(sample_path, "r", encoding="utf-8") as f:
                    agreement_text = f.read()
                st.text_area("Agreement Text (PII Expunged)", agreement_text, height=320)
            else:
                st.warning(f"Sample agreement file not found at `{sample_path}`.")
                agreement_text = ""

            ingest_btn = st.button("📥 Ingest & Index Agreement into ChromaDB", use_container_width=True)
            if ingest_btn and agreement_text:
                with st.spinner("Chunking agreement clauses and indexing into ChromaDB..."):
                    try:
                        res = api_client.upload_document(
                            file_bytes=agreement_text.encode("utf-8"),
                            filename="sample_redacted_rent_agreement.txt",
                            document_type="other",
                            policy_id=1,  # Associated under default portfolio
                        )
                        st.success(f"Agreement indexed! Created {res.get('total_chunks', 0)} searchable clause chunks.")
                    except Exception as e:
                        st.error(f"Ingestion failed: {e}")

        with col_right:
            st.markdown("#### 2. Query Agreement Terms (Semantic Search)")
            st.markdown("Select a sample auditor query or type a custom question:")

            sample_queries = [
                "What is the lock-in period and penalty for early termination?",
                "When is the security deposit refunded and what deductions are permitted?",
                "Are tenants allowed to sublet or license the apartment?",
                "Who is responsible for routine day-to-day minor repairs?",
            ]

            selected_query = st.selectbox("Sample Legal Queries", sample_queries)
            custom_query = st.text_input("Or custom search query", value=selected_query)

            query_btn = st.button("🔍 Retrieve Grounded Clauses", type="primary", use_container_width=True)

            if query_btn and custom_query.strip():
                with st.spinner("Searching ChromaDB vector store..."):
                    try:
                        search_res = api_client.search_documents(
                            query=custom_query.strip(),
                            top_k=3,
                            document_type="other",
                        )
                        results = search_res.get("results", [])
                        st.markdown(f"**Found {len(results)} relevant contract clauses:**")

                        for idx, r in enumerate(results, 1):
                            dist = r.get("similarity_score")
                            dist_str = f"Distance: {dist:.4f}" if dist is not None else ""
                            st.markdown(
                                f"""
                                <div style="background: #F1F5F9; border-left: 3px solid #0284C7; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;">
                                    <div style="font-weight: 700; color: #0F172A; font-size: 0.90rem;">
                                        Clause Reference: {r.get('clause_or_section_ref') or 'Lease Section'} {dist_str}
                                    </div>
                                    <div style="font-size: 0.84rem; color: #334155; margin-top: 4px; white-space: pre-wrap;">
{r.get('text', '')[:350]}...
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                    except Exception as e:
                        st.error(f"Retrieval error: {e}")
