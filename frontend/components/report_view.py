"""Audit Report and Recommendation View Component for ClauseGuard."""

from typing import Any, Dict, Optional
import streamlit as st


def render_report_view(
    report_data: Optional[Dict[str, Any]] = None,
    api_client: Optional[Any] = None,
):
    """Renders structured, explainable claim audit report and advisory verdict."""
    st.subheader("📑 Claim Audit & Evidence Report")

    if not report_data:
        st.info(
            "No active audit report loaded. Please go to **Sample Case** and click **Load & Audit Sample Case**, "
            "or trigger an analysis on a registered claim."
        )
        return

    report_id = report_data.get("report_id") or report_data.get("id")
    claim_id = report_data.get("claim_id")
    agent_trace = report_data.get("agent_trace") or {}
    override_data = agent_trace.get("override")

    # --------------------------------------------------------------------------
    # 1. VERDICT HEADER & OVERRIDE CALLOUT
    # --------------------------------------------------------------------------
    verdict = str(report_data.get("verdict", "REVIEW_REQUIRED")).upper()
    if "TAKE" in verdict and "DO_NOT" not in verdict:
        badge_color = "#16A34A"
        badge_bg = "#DCFCE7"
        badge_border = "#86EFAC"
        badge_icon = "✅"
        badge_label = "TAKE (RECOMMENDED FOR APPROVAL)"
    elif "DO_NOT_TAKE" in verdict:
        badge_color = "#DC2626"
        badge_bg = "#FEE2E2"
        badge_border = "#FCA5A5"
        badge_icon = "🛑"
        badge_label = "DO NOT TAKE (CRITICAL BLOCKERS DETECTED)"
    else:
        badge_color = "#D97706"
        badge_bg = "#FEF3C7"
        badge_border = "#FCD34D"
        badge_icon = "⚠️"
        badge_label = "REVIEW REQUIRED (MANUAL ESCALATION)"

    if override_data:
        badge_label += " [OVERRIDDEN]"

    fallback_used = report_data.get("fallback_used", False)
    fallback_reason = report_data.get("fallback_reason")

    col_v1, col_v2 = st.columns([2, 1])

    with col_v1:
        st.markdown(
            f"""
            <div style="background: {badge_bg}; border: 2px solid {badge_border}; border-radius: 12px; padding: 16px 20px; margin-bottom: 16px;">
                <div style="font-size: 0.82rem; font-weight: 700; color: #475569; text-transform: uppercase; letter-spacing: 0.5px;">
                    Advisory Decision-Support Recommendation
                </div>
                <div style="font-size: 1.6rem; font-weight: 800; color: {badge_color}; margin-top: 4px;">
                    {badge_icon} {badge_label}
                </div>
                <div style="font-size: 0.85rem; color: #475569; margin-top: 6px;">
                    <em>Notice: Advisory recommendation only. Does not constitute a binding legal adjudication or automated payment/denial.</em>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_v2:
        risk_score = report_data.get("overall_risk_score", 0.0)
        confidence = report_data.get("confidence_score", 0.85)

        st.markdown(
            f"""
            <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 16px; margin-bottom: 16px;">
                <div style="font-size: 0.82rem; font-weight: 700; color: #64748B;">DETERMINISTIC RISK SCORE</div>
                <div style="font-size: 1.8rem; font-weight: 800; color: #1E293B;">
                    {risk_score:.1f} <span style="font-size: 1.0rem; color: #64748B;">/ 100</span>
                </div>
                <div style="font-size: 0.80rem; color: #64748B; margin-top: 4px;">
                    Confidence: {confidence * 100:.0f}% <em>(heuristic metric)</em>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Active Override Banner if present
    if override_data:
        st.markdown(
            f"""
            <div style="background: #EFF6FF; border: 1px solid #93C5FD; border-left: 5px solid #2563EB; border-radius: 8px; padding: 12px 18px; margin-bottom: 14px;">
                <div style="font-size: 0.95rem; font-weight: 700; color: #1E3A8A;">
                    ⚖️ Senior Adjudicator Formal Verdict Override Active
                </div>
                <div style="font-size: 0.88rem; color: #1E293B; margin-top: 4px;">
                    <strong>Original Workflow Verdict:</strong> <code>{override_data.get('original_verdict')}</code> &nbsp;→&nbsp;
                    <strong>Adjudicated Final Verdict:</strong> <code>{override_data.get('final_verdict')}</code>
                </div>
                <div style="font-size: 0.82rem; color: #3B82F6; margin-top: 4px;">
                    <strong>Signed by:</strong> {override_data.get('adjudicator_name')} &bull;
                    <strong>Timestamp:</strong> {override_data.get('timestamp')}
                </div>
                <div style="font-size: 0.85rem; color: #475569; margin-top: 6px; background: #FFFFFF; padding: 8px 12px; border-radius: 6px; border: 1px solid #DBEAFE;">
                    <strong>Justification:</strong> {override_data.get('justification')}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Prominent Fallback Warning if applicable
    if fallback_used:
        st.warning(
            f"""
            ⚡ **Model Fallback Notice**: This claim analysis was generated under a model fallback or degraded mode
            ({fallback_reason or 'local heuristic / mock provider active'}). All conclusions must be manually verified by a senior claims adjudicator.
            """,
            icon="⚠️",
        )

    # Claim & Policy Metadata Summary
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Claim ID", claim_id or "N/A")
    m2.metric("Claimant", report_data.get("claimant_name", "N/A"))
    m3.metric("Policy Number", report_data.get("policy_number", "N/A"))
    m4.metric("Discrepancies", len(report_data.get("fraud_signals", [])))

    st.markdown("<hr style='margin: 16px 0; border-color: #E2E8F0;'/>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # 2. EXECUTIVE PDF EXPORT & ADJUDICATOR DIGITAL SIGN-OFF BAR
    # --------------------------------------------------------------------------
    st.markdown("### 📥 Publication Export & Digital Sign-Off")
    exp_col1, exp_col2 = st.columns([1, 1])

    with exp_col1:
        st.markdown("#### 📄 Executive PDF Audit Report")
        st.caption("Generate a regulator-ready PDF summary with source-grounded evidence and audit logs.")
        pdf_storage_key = f"cached_pdf_{report_id or claim_id}"

        if api_client and (report_id or claim_id):
            if pdf_storage_key not in st.session_state:
                if st.button("📥 Compile Executive PDF Report", use_container_width=True):
                    with st.spinner("Rendering publication-ready PDF via ReportLab..."):
                        try:
                            if report_id:
                                p_data = api_client.export_report_pdf(report_id)
                            else:
                                p_data = api_client.export_claim_report_pdf(claim_id)
                            st.session_state[pdf_storage_key] = p_data
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to generate PDF: {e}")
            else:
                st.download_button(
                    label="💾 Download Executive Audit Report (PDF)",
                    data=st.session_state[pdf_storage_key],
                    file_name=f"ClauseGuard_Audit_Report_{report_id or claim_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
        else:
            st.info("API Client not connected or report reference missing.")

    with exp_col2:
        st.markdown("#### ⚖️ Adjudicator Verdict Override")
        current_role = getattr(api_client, "role", "AUDITOR") if api_client else "AUDITOR"
        current_operator = getattr(api_client, "operator_name", "Staff Claims Auditor") if api_client else "Staff Claims Auditor"

        if current_role != "SENIOR_ADJUDICATOR":
            st.info(
                f"👤 Current Role: **{current_role}** (Auditor privileges: View & Export).\n\n"
                "To record a binding digital sign-off or verdict override, switch your role to **SENIOR_ADJUDICATOR** in the left sidebar."
            )
        else:
            with st.expander("📝 Senior Adjudicator Formal Sign-Off Panel", expanded=False):
                with st.form(key=f"override_form_{report_id or claim_id}"):
                    new_verdict = st.selectbox(
                        "Final Adjudicated Verdict",
                        options=["TAKE", "REVIEW_REQUIRED", "DO_NOT_TAKE"],
                        index=0 if "TAKE" in verdict and "DO_NOT" not in verdict else (2 if "DO_NOT_TAKE" in verdict else 1),
                        help="Select the legally binding adjudication verdict.",
                    )
                    adj_name = st.text_input("Senior Adjudicator Name", value=current_operator)
                    justification = st.text_area(
                        "Adjudication Justification & Legal Basis",
                        placeholder="Provide explicit rationale, risk assessment, or regulatory basis for overriding or signing off this verdict...",
                        rows=3,
                    )
                    submit_override = st.form_submit_button("Commit Formal Digital Sign-Off", type="primary")

                    if submit_override:
                        if not justification.strip():
                            st.error("A comprehensive legal/factual justification is required to execute a verdict override.")
                        elif not report_id:
                            st.error("Report ID reference missing. Ensure claim analysis has been persisted to SQLite.")
                        else:
                            try:
                                res = api_client.override_report_verdict(
                                    report_id=report_id,
                                    final_verdict=new_verdict,
                                    adjudicator_name=adj_name,
                                    justification=justification.strip(),
                                )
                                # Clear cached PDF so newly exported PDF will reflect the sign-off
                                if pdf_storage_key in st.session_state:
                                    del st.session_state[pdf_storage_key]

                                # Update session state report
                                report_data["verdict"] = new_verdict
                                if "agent_trace" not in report_data or not isinstance(report_data["agent_trace"], dict):
                                    report_data["agent_trace"] = {}
                                report_data["agent_trace"]["override"] = {
                                    "original_verdict": res.get("original_verdict"),
                                    "final_verdict": res.get("final_verdict"),
                                    "adjudicator_name": res.get("adjudicator_name"),
                                    "justification": res.get("justification"),
                                    "timestamp": res.get("timestamp"),
                                }
                                st.session_state["active_report"] = report_data
                                st.success("Verdict override successfully committed to immutable AuditLog!")
                                st.rerun()
                            except Exception as err:
                                st.error(f"Failed to record sign-off: {err}")

    st.markdown("<hr style='margin: 16px 0; border-color: #E2E8F0;'/>", unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # 2. FINANCIAL CALCULATIONS BREAKDOWN (Pure Python Arithmetic)
    # --------------------------------------------------------------------------
    st.markdown("### 🧮 Pure Python Deterministic Calculations")
    calcs = report_data.get("calculations", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Claimed Amount", f"${calcs.get('claimed_amount', 0.0):,.2f}")
    c2.metric("Room Excess Deduction", f"-${calcs.get('room_excess_deduction', 0.0):,.2f}")
    c3.metric("Exclusion Deduction", f"-${calcs.get('exclusion_deduction', 0.0):,.2f}")
    c4.metric("Net Eligible Amount", f"${calcs.get('net_eligible_amount', 0.0):,.2f}")

    with st.expander("Detailed Calculation Audit Steps", expanded=True):
        steps = calcs.get("calculation_steps", [])
        if steps:
            for s in steps:
                st.markdown(f"- `{s}`")
        else:
            st.write("No calculation audit steps recorded.")

        d_sub = calcs.get("room_sub_limit_applied")
        if d_sub:
            st.info(f"Policy Room & Board Sub-Limit applied: **${d_sub:,.2f}/day** (4-day stay cap: **${d_sub * 4:,.2f}**)")

    # --------------------------------------------------------------------------
    # 3. TRACK A: FRAUD SIGNALS & CONTRADICTIONS
    # --------------------------------------------------------------------------
    st.markdown("### 🚩 Track A — Claim Fraud Indicators & Objective Inconsistencies")
    signals = report_data.get("fraud_signals", [])

    if signals:
        for idx, sig in enumerate(signals, 1):
            sev = str(sig.get("severity", "")).upper()
            if "CRITICAL" in sev:
                s_icon, s_color = "🔴", "#DC2626"
            elif "HIGH" in sev:
                s_icon, s_color = "🟠", "#EA580C"
            else:
                s_icon, s_color = "🟡", "#CA8A04"

            st.markdown(
                f"""
                <div style="background: #FFFFFF; border-left: 4px solid {s_color}; border-top: 1px solid #E2E8F0; border-right: 1px solid #E2E8F0; border-bottom: 1px solid #E2E8F0; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-weight: 700; color: #1E293B;">{s_icon} {sig.get('title')}</span>
                        <span style="font-size: 0.75rem; font-weight: 700; color: {s_color}; border: 1px solid {s_color}; padding: 2px 8px; border-radius: 10px;">{sev}</span>
                    </div>
                    <div style="color: #475569; font-size: 0.90rem; margin-top: 6px;">
                        {sig.get('description')}
                    </div>
                    <div style="font-size: 0.82rem; color: #64748B; margin-top: 6px;">
                        <strong>Action:</strong> {sig.get('suggested_action') or 'Verify with records'} |
                        <strong>Policy Citation:</strong> <code>{sig.get('policy_reference') or 'General Terms'}</code>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.success("No objective fraud indicators or document contradictions detected.")

    st.caption("ℹ️ Inconsistencies and document discrepancies alone do not constitute legal proof of intentional fraud.")

    # --------------------------------------------------------------------------
    # 4. MISSING MANDATORY DOCUMENTS
    # --------------------------------------------------------------------------
    missing_docs = report_data.get("missing_documents", [])
    if missing_docs:
        st.markdown("### 📋 Missing Required Documentation")
        for doc in missing_docs:
            st.error(f"Missing Mandatory Document: **{doc}**")

    # --------------------------------------------------------------------------
    # 5. TRACK B: POLICY LOOPHOLES & CONTRACT AMBIGUITY (Separated from fraud)
    # --------------------------------------------------------------------------
    st.markdown("### 🔍 Track B — Policy / Scheme Loopholes & Ambiguity")
    st.caption("Policy contract ambiguities and coverage gaps are strictly separated from claim fraud indicators.")
    loopholes = report_data.get("policy_loopholes", [])

    if loopholes:
        for lh in loopholes:
            st.markdown(
                f"""
                <div style="background: #F8FAFC; border: 1px solid #CBD5E1; border-left: 4px solid #6366F1; border-radius: 8px; padding: 12px 16px; margin-bottom: 10px;">
                    <div style="font-weight: 700; color: #1E293B;">
                        ⚡ [{lh.get('clause_reference')}] {lh.get('loophole_type')}
                    </div>
                    <div style="color: #334155; font-size: 0.90rem; margin-top: 4px;">
                        {lh.get('description')}
                    </div>
                    <div style="font-size: 0.82rem; color: #4338CA; margin-top: 6px;">
                        <strong>Potential Underwriter Risk:</strong> {lh.get('potential_risk')}
                    </div>
                    <div style="font-size: 0.82rem; color: #047857; margin-top: 2px;">
                        <strong>Suggested Contract Remedy:</strong> {lh.get('suggested_remedy')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("No policy loopholes or drafting ambiguities detected in reviewed clauses.")

    # --------------------------------------------------------------------------
    # 6. VERDICT EXPLANATION & ACTIONABLE CONDITIONS
    # --------------------------------------------------------------------------
    st.markdown("### 🎯 Decision Rationale & Next Steps")
    col_r1, col_r2 = st.columns(2)

    with col_r1:
        st.markdown("#### Top Decision Drivers")
        reasons = report_data.get("top_reasons", [])
        if reasons:
            for r in reasons:
                st.markdown(f"- {r}")
        else:
            st.write("No explicit decision drivers noted.")

    with col_r2:
        st.markdown("#### Conditions to Alter Verdict")
        conditions = report_data.get("conditions_to_change_verdict", [])
        if conditions:
            for c in conditions:
                st.markdown(f"- 📌 {c}")
        else:
            st.write("None. Decision ready for final human sign-off.")

    # --------------------------------------------------------------------------
    # 7. APPROVED CLAUSE CITATIONS
    # --------------------------------------------------------------------------
    with st.expander("📚 Reviewer-Approved Policy Clauses Citation List", expanded=False):
        approved = report_data.get("approved_clause_refs", [])
        if approved:
            st.markdown(f"**Total Approved Clauses:** {len(approved)}")
            for ref in approved:
                st.markdown(f"- Clause Citation: `{ref}`")
        else:
            st.write("No approved clause citations available.")
