"""ClauseGuard - Auditor Dashboard.

Streamlit frontend entry point for explainable AI insurance claim auditing,
clause-aware document retrieval, and policy loophole detection.
"""

import os
import streamlit as st
from frontend.api_client import ClauseGuardAPIClient
from frontend.components.header import render_header
from frontend.components.sample_loader import render_sample_case_loader
from frontend.components.upload_search import render_upload_and_search
from frontend.components.report_view import render_report_view
from frontend.components.exhibition_demo import render_exhibition_demo

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="ClauseGuard - Auditor Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    /* Global Styles */
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2.5rem;
    }
    /* Metric Card Styling */
    div[data-testid="metric-container"] {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 12px 16px;
    }
    /* Expander Border */
    div[data-testid="stExpander"] {
        border-radius: 8px;
        border: 1px solid #E2E8F0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize API Client
api_url = os.getenv("CLAUSEGUARD_API_URL", "http://127.0.0.1:8000/api/v1")
api_client = ClauseGuardAPIClient(base_url=api_url)

# Render Top Header
render_header(api_client)

# Live Demo Bar / Quick Launch Panel
st.markdown("---")
col_demo1, col_demo2, col_demo3 = st.columns([2, 2, 1])
with col_demo1:
    if st.button("Preset 1: Insurance Claim Sample", key="preset1"):
        try:
            res = api_client.trigger_claim_analysis(1)
            st.session_state["active_report"] = res
            st.session_state["active_claim_id"] = 1
            st.success("✅ Sample claim loaded and analysis completed.")
            # Switch view to report
            st.session_state["_selected_page"] = "📑 Audit Report"
            st.rerun()
        except Exception as e:
            st.error(f"Failed to run Preset 1: {e}")
with col_demo2:
    if st.button("Preset 2: Rent Agreement Demo", key="preset2"):
        # Set flag for exhibition demo to start Scenario 2 automatically
        st.session_state["exhibition_demo_preset"] = "Scenario 2"
        st.session_state["_selected_page"] = "🎪 Exhibition Demo"
        st.rerun()
with col_demo3:
    if st.button("Reset Demo State", key="reset_demo"):
        try:
            resp = api_client.reset_demo_state()
            st.success("Demo state reset successfully.")
            # Clear cached session data
            for k in list(st.session_state.keys()):
                if k.startswith("active_"):
                    del st.session_state[k]
            # Refresh page
            st.rerun()
        except Exception as e:
            st.error(f"Reset failed: {e}")







# Sidebar Navigation
with st.sidebar:
    st.markdown("### 🧭 Navigation")
    selected_page = st.radio(
        "Select Workspace View",
        options=[
            "🏠 Dashboard Overview",
            "📁 Sample Case",
            "📤 Upload & Search",
            "📑 Audit Report",
            "🎪 Exhibition Demo",
        ],
        index=0,
        key="nav_radio",
    )
    # Persist selection for preset routing
st.session_state["_selected_page"] = selected_page


# If a preset button set a new page, use that value
selected_page = st.session_state.get("_selected_page", selected_page)

st.markdown("---")

# System Environment
st.markdown("### ⚙️ System Environment")
st.caption(f"**Backend API:** `{api_client.base_url}`")
try:
    sys_status = api_client.get_system_status()
    st.caption(f"**Environment:** `{sys_status.get('environment', 'local')}`")
    st.caption(f"**DB Status:** `{sys_status.get('database', {}).get('status', 'unknown')}`")
    st.caption(f"**LLM:** `{sys_status.get('llm_provider', {}).get('status', 'unknown')}`")
except Exception:
    st.caption("**Backend Status:** `Offline / Unreachable`")

st.markdown("---")
st.markdown(
        """
        <div style="font-size: 0.75rem; color: #94A3B8; text-align: center;">
            ClauseGuard v0.1.0 • Wave 4<br/>
            Explainable AI Insurance Intelligence
        </div>
        """,
        unsafe_allow_html=True,
    )

# ------------------------------------------------------------------------------
# PAGE ROUTING
# ------------------------------------------------------------------------------
if selected_page == "🏠 Dashboard Overview":
    st.subheader("📊 System Dashboard & Activity Overview")
    st.markdown(
            """
            ClauseGuard is an explainable AI document intelligence platform that protects insurance providers
            and claimants by automating **cross-document fraud detection**, **clause contradiction analysis**,
            and **policy loophole identification**.
            """
        )

    try:
            status_data = api_client.get_system_status()
            counts = status_data.get("counts", {})
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Active Policies", counts.get("policies", 0))
            col2.metric("Audited Claims", counts.get("claims", 0))
            col3.metric("Flagged Discrepancies", counts.get("findings", 0))
            col4.metric("Vector Index", "ChromaDB Ready ✓")
    except Exception:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Active Policies", "1 (Default)")
        col2.metric("Audited Claims", "1 (Sample)")
        col3.metric("Flagged Discrepancies", "4")
        col4.metric("Vector Index", "ChromaDB (Offline)")

    st.markdown("### ⚡ Quick Actions")
    qa1, qa2, qa3 = st.columns(3)
    with qa1:
        st.markdown(
            """
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px;">
                <h4>📁 1-Click Sample Audit</h4>
                <p style="color: #64748B; font-size: 0.88rem;">Load built-in Claim CLM-2026-8801 and run full LangGraph analysis pipeline.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with qa2:
            st.markdown(
                """
                <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px;">
                    <h4>📤 Ingest New Documents</h4>
                    <p style="color: #64748B; font-size: 0.88rem;">Upload itemized hospital invoices, claims, or policy PDFs with OCR support.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with qa3:
            st.markdown(
                """
                <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 16px;">
                    <h4>🎪 Exhibition Live Demo</h4>
                    <p style="color: #64748B; font-size: 0.88rem;">Interactive showcase for health insurance audit & redacted rent agreements.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("### 🔄 LangGraph Analysis Pipeline Architecture")
    st.markdown(
            """
            ```mermaid
            flowchart LR
                A["Claim & Evidence Retrieval"] --> B["Policy Rule Extraction"]
                B --> C["Reviewer Applicability Gate"]
                C --> D["Analyzer & Calculator"]
                D --> E["Deterministic Recommendation Gate"]
                E --> F["Audit Report & Log Persistence"]
            ```
            """
        )

elif selected_page == "📁 Sample Case":
    render_sample_case_loader(api_client)

elif selected_page == "📤 Upload & Search":
    render_upload_and_search(api_client)

elif selected_page == "📑 Audit Report":
    active_rep = st.session_state.get("active_report")
    if not active_rep and api_client.is_connected():
        # Attempt to auto-fetch latest report for Claim 1
        try:
            active_rep = api_client.get_latest_claim_analysis(1)
            st.session_state["active_report"] = active_rep
        except Exception:
            pass
    render_report_view(active_rep)

elif selected_page == "🎪 Exhibition Demo":
    render_exhibition_demo(api_client)
