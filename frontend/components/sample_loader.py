"""Sample Case Loader Component for ClauseGuard."""

from pathlib import Path
import streamlit as st
from frontend.api_client import ClauseGuardAPIClient, APIClientError


def render_sample_case_loader(api_client: ClauseGuardAPIClient):
    """Renders the self-contained One-Click Sample Case loader."""
    st.subheader("📁 Built-in Exhibition Sample Case")
    st.markdown(
        """
        Load and audit the built-in insurance benchmark claim package (**Apex Mutual Assurance — Claim `CLM-2026-8801`**).
        This executes the complete LangGraph analysis pipeline:
        **Retrieval → Policy Rule Extraction → Reviewer Gate → Analyzer & Calculator → Deterministic Recommendation Gate → Audit Report Persistence**.
        """
    )

    with st.expander("ℹ️ Inspect Sample Claim Pack Details", expanded=False):
        st.markdown(
            """
            - **Policy**: `POL-SHIELD-2026-8801` (Comprehensive Health Shield Contract)
            - **Claimant**: David K. Vance
            - **Claim Amount**: **$9,570.00**
            - **Effective Date**: February 1, 2026
            - **Incident Date**: February 15, 2026 (14 days after inception)
            - **Included Files**:
              1. `sample_data/policies/apex_shield_policy.pdf` (Policy Contract)
              2. `sample_data/claims/claim_form_clm_8801.pdf` (Claim Declaration Form)
              3. `sample_data/invoices/st_jude_medical_invoice.pdf` (Hospital Invoice with itemized charges)
              4. `sample_data/evidence/physician_notes.txt` (Attending Physician Memorandum)
            - **Planted Scenarios**:
              - *Scenario B*: 14-day loss violating mandatory 30-day waiting period.
              - *Scenario C*: $3,200 Cosmetic Rhinoplasty excluded under Section 4.1; $400 room sub-limit excess.
              - *Scenario D*: Missing formal discharge summary.
              - *Scenario E*: Ambiguous Clause 9.3 alternative therapy discretionary wording ($1,100).
            """
        )

    col1, col2 = st.columns([1, 2])

    with col1:
        load_btn = st.button("🚀 Load & Audit Sample Case", type="primary", use_container_width=True)

    if load_btn:
        with st.status("Processing Claim CLM-2026-8801 through LangGraph...", expanded=True) as status:
            try:
                st.write("1. Connecting to ClauseGuard backend...")
                if not api_client.is_connected():
                    status.update(label="Backend Unreachable", state="error")
                    st.error(
                        f"Cannot connect to ClauseGuard backend at `{api_client.base_url}`. "
                        "Please verify the FastAPI server is running."
                    )
                    return

                # Find claim 1 or seed it if empty
                st.write("2. Locating sample claim in SQLite database...")
                claims = api_client.list_claims()
                target_claim_id = None
                for c in claims:
                    if c.get("claim_number") == "CLM-2026-8801":
                        target_claim_id = c.get("id")
                        break

                if not target_claim_id:
                    st.write("3. Seeding sample pack from sample_data/...")
                    try:
                        from sample_data.ingest_samples import seed_database_and_ingest
                        seed_database_and_ingest()
                        claims = api_client.list_claims()
                        for c in claims:
                            if c.get("claim_number") == "CLM-2026-8801":
                                target_claim_id = c.get("id")
                                break
                    except Exception as e:
                        st.warning(f"Direct seed skipped: {e}. Checking API claims list...")

                if not target_claim_id:
                    target_claim_id = 1  # Standard default sample claim ID

                st.write(f"4. Executing LangGraph analysis workflow for Claim ID {target_claim_id}...")
                report = api_client.trigger_claim_analysis(target_claim_id)

                status.update(label="Sample Case Audited Successfully!", state="complete", expanded=False)
                st.success(f"Audit completed for Claim CLM-2026-8801 (Report ID: {report.get('report_id', target_claim_id)})!")

                # Store report in session state for instant view
                st.session_state["active_report"] = report
                st.session_state["active_claim_id"] = target_claim_id

            except APIClientError as e:
                status.update(label="Analysis Failed", state="error")
                st.error(f"Backend API error: {e}")
            except Exception as e:
                status.update(label="Unexpected Error", state="error")
                st.error(f"Failed to process sample case: {str(e)}")

    # If active report in session state, render shortcut message
    if "active_report" in st.session_state:
        st.info("💡 An active analysis report is loaded in session. Switch to the **Audit Report** tab to explore findings!")
