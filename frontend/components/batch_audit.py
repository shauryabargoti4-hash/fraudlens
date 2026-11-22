"""Batch Portfolio Audit Component for ClauseGuard.

Provides multi-claim auditing capabilities across portfolios, executing sequential
LangGraph analysis with error isolation, aggregate metrics, and direct PDF export.
"""

from typing import Any, Dict, List, Optional
import streamlit as st
from frontend.api_client import ClauseGuardAPIClient, APIClientError


def render_batch_audit(api_client: ClauseGuardAPIClient):
    """Renders the Multi-Claim Batch Portfolio Audit workspace."""
    st.subheader("📦 Multi-Claim Portfolio Batch Audit")
    st.markdown(
        """
        Execute parallel/sequential portfolio-level audits across multiple insurance claims.
        ClauseGuard processes each claim through the complete evidence extraction,
        clause review, and deterministic calculation pipeline with **strict per-claim error isolation**.
        """
    )

    if not api_client.is_connected():
        st.error(
            f"Cannot connect to ClauseGuard backend at `{api_client.base_url}`. "
            "Please ensure the backend is running."
        )
        return

    # Fetch available policies and claims from backend
    try:
        available_claims = api_client.list_claims()
    except Exception as e:
        available_claims = []
        st.warning(f"Unable to fetch existing claims list: {e}")

    try:
        available_policies = api_client.list_policies()
    except Exception as e:
        available_policies = []
        st.warning(f"Unable to fetch existing policies list: {e}")

    # Audit Selection Mode
    mode = st.radio(
        "Audit Selection Mode",
        options=["Select Specific Claims", "Audit Entire Policy Portfolio", "Manual Comma-Separated IDs"],
        horizontal=True,
    )

    selected_claim_ids: List[int] = []
    selected_policy_id: Optional[int] = None

    if mode == "Select Specific Claims":
        if available_claims:
            claim_options = {
                f"Claim #{c.get('id')} ({c.get('claim_number', 'N/A')}) - {c.get('claimant_name', 'Unknown')} (${c.get('claimed_amount', 0.0):,.2f})": c.get("id")
                for c in available_claims
            }
            selected_labels = st.multiselect(
                "Select Claims to Audit",
                options=list(claim_options.keys()),
                default=list(claim_options.keys())[:min(5, len(claim_options))],
                help="Select one or more claims to audit concurrently.",
            )
            selected_claim_ids = [claim_options[label] for label in selected_labels]
        else:
            st.info("No claims currently found in database. Ingest sample data or use manual ID entry.")

    elif mode == "Audit Entire Policy Portfolio":
        if available_policies:
            policy_options = {
                f"Policy #{p.get('id')} ({p.get('policy_number', 'N/A')}) - {p.get('policy_holder_name', 'Unknown')}": p.get("id")
                for p in available_policies
            }
            selected_p_label = st.selectbox("Select Target Policy", options=list(policy_options.keys()))
            if selected_p_label:
                selected_policy_id = policy_options[selected_p_label]
        else:
            st.info("No policies currently found in database.")

    else:
        id_str = st.text_input("Enter Claim IDs (comma-separated)", value="1")
        if id_str.strip():
            try:
                selected_claim_ids = [int(x.strip()) for x in id_str.split(",") if x.strip().isdigit()]
            except Exception:
                selected_claim_ids = []

    # Run Batch Audit Trigger
    st.markdown("---")
    can_run = bool(selected_claim_ids or selected_policy_id)
    run_btn = st.button("🚀 Run Portfolio Batch Audit", type="primary", disabled=not can_run)

    if run_btn:
        progress_bar = st.progress(0, text="Initializing Portfolio Batch Audit...")
        with st.spinner("Executing LangGraph analysis across claim portfolio..."):
            try:
                progress_bar.progress(20, text="Dispatching claims to ClauseGuard pipeline...")
                batch_response = api_client.batch_audit_claims(
                    claim_ids=selected_claim_ids if selected_claim_ids else None,
                    policy_id=selected_policy_id,
                )
                progress_bar.progress(100, text="Portfolio Audit Completed!")
                st.session_state["latest_batch_result"] = batch_response
                st.success(
                    f"Batch audit completed! Processed {batch_response.get('processed_count', 0)} claims "
                    f"({batch_response.get('success_count', 0)} succeeded, {batch_response.get('failed_count', 0)} failed)."
                )
            except APIClientError as e:
                progress_bar.progress(100, text="Batch audit encountered an error.")
                st.error(f"Batch audit failed: {e}")
            except Exception as e:
                progress_bar.progress(100, text="Batch audit failed.")
                st.error(f"Unexpected error during batch execution: {e}")

    # Render Batch Results if Available
    batch_result = st.session_state.get("latest_batch_result")
    if batch_result:
        st.markdown("### 📊 Portfolio Audit Summary Metrics")
        m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
        m_col1.metric("Claims Processed", batch_result.get("processed_count", 0))
        m_col2.metric("Successful Audits", batch_result.get("success_count", 0))
        m_col3.metric("Failed / Errors", batch_result.get("failed_count", 0))

        v_counts = batch_result.get("verdict_counts", {})
        take_c = v_counts.get("TAKE", 0)
        review_c = v_counts.get("REVIEW_REQUIRED", 0)
        dnt_c = v_counts.get("DO_NOT_TAKE", 0)

        m_col4.metric("Approval Recommended (TAKE)", take_c)
        m_col5.metric("Review / Blocked", f"{review_c} rev / {dnt_c} blk")

        # Breakdown visual bar
        st.markdown("---")
        st.markdown("### 📋 Audited Claims Register")

        results_list = batch_result.get("results", [])
        if not results_list:
            st.info("No claim results to display.")
            return

        for item in results_list:
            c_id = item.get("claim_id")
            success = item.get("success", False)
            verdict = str(item.get("verdict", "N/A")).upper()
            c_num = item.get("claim_number", f"ID-{c_id}")
            claimant = item.get("claimant_name", "N/A")
            claimed = item.get("claimed_amount", 0.0)
            eligible = item.get("net_eligible_amount", 0.0)
            risk = item.get("risk_score", 0.0)
            error = item.get("error")

            if not success:
                st.error(f"❌ **Claim #{c_id} ({c_num})** — Error: {error}")
                continue

            if "TAKE" in verdict and "DO_NOT" not in verdict:
                v_badge = "🟢 TAKE (Eligible)"
                b_color = "#DCFCE7"
            elif "DO_NOT_TAKE" in verdict:
                v_badge = "🔴 DO NOT TAKE"
                b_color = "#FEE2E2"
            else:
                v_badge = "🟡 REVIEW REQUIRED"
                b_color = "#FEF3C7"

            with st.container():
                st.markdown(
                    f"""
                    <div style="background: {b_color}; border: 1px solid #CBD5E1; border-radius: 8px; padding: 12px 16px; margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="font-weight: 800; font-size: 1.05rem; color: #1E293B;">
                                    Claim #{c_id} &bull; {c_num} ({claimant})
                                </span>
                                <div style="font-size: 0.85rem; color: #475569; margin-top: 3px;">
                                    Claimed: <strong>${claimed:,.2f}</strong> &bull;
                                    Net Eligible: <strong>${eligible:,.2f}</strong> &bull;
                                    Risk Score: <strong>{risk:.1f}/100</strong>
                                </div>
                            </div>
                            <div style="text-align: right;">
                                <span style="font-weight: 800; font-size: 0.95rem; color: #1E293B;">{v_badge}</span>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                row_c1, row_c2, _ = st.columns([1, 1, 2])
                with row_c1:
                    if st.button(f"📑 Inspect Report #{c_id}", key=f"view_rep_{c_id}", use_container_width=True):
                        try:
                            rep = api_client.get_latest_claim_analysis(c_id)
                            st.session_state["active_report"] = rep
                            st.session_state["active_claim_id"] = c_id
                            st.success(f"Report for Claim #{c_id} loaded into active workspace! Switch to '📑 Audit Report' view.")
                        except Exception as err:
                            st.error(f"Failed to fetch report: {err}")

                with row_c2:
                    pdf_btn_key = f"dl_batch_pdf_{c_id}"
                    if pdf_btn_key not in st.session_state:
                        if st.button(f"📄 Fetch PDF #{c_id}", key=f"btn_pdf_{c_id}", use_container_width=True):
                            with st.spinner("Generating PDF..."):
                                try:
                                    pdf_bytes = api_client.export_claim_report_pdf(c_id)
                                    st.session_state[pdf_btn_key] = pdf_bytes
                                    st.rerun()
                                except Exception as err:
                                    st.error(f"PDF export failed: {err}")
                    else:
                        st.download_button(
                            label=f"💾 Save PDF #{c_id}",
                            data=st.session_state[pdf_btn_key],
                            file_name=f"ClauseGuard_Audit_Report_Claim_{c_id}.pdf",
                            mime="application/pdf",
                            key=f"dl_ready_{c_id}",
                            use_container_width=True,
                        )
