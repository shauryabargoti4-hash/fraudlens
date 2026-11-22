"""Header Component for ClauseGuard Streamlit App."""

import streamlit as st
from frontend.api_client import ClauseGuardAPIClient


def render_header(api_client: ClauseGuardAPIClient):
    """Renders the top branding header and live backend connection badge."""
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
                <span style="font-size: 2.2rem;">🛡️</span>
                <span style="font-size: 2.0rem; font-weight: 700; letter-spacing: -0.5px; color: #1E293B;">
                    ClauseGuard
                </span>
                <span style="background: #EEF2F6; color: #475569; font-size: 0.75rem; font-weight: 600; padding: 2px 8px; border-radius: 12px; border: 1px solid #CBD5E1;">
                    v0.1.0 • Wave 4
                </span>
            </div>
            <p style="color: #64748B; font-size: 0.95rem; margin-top: 0px; margin-bottom: 12px;">
                Explainable AI Claim Auditing, Clause Verification & Policy Loophole Detection
            </p>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        try:
            health = api_client.get_health()
            if health.get("status") == "healthy":
                st.markdown(
                    """
                    <div style="text-align: right; padding-top: 8px;">
                        <span style="background: #DCFCE7; color: #166534; font-size: 0.82rem; font-weight: 600; padding: 5px 12px; border-radius: 16px; border: 1px solid #86EFAC;">
                            ● API Connected (8000)
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """
                    <div style="text-align: right; padding-top: 8px;">
                        <span style="background: #FEF9C3; color: #854D0E; font-size: 0.82rem; font-weight: 600; padding: 5px 12px; border-radius: 16px; border: 1px solid #FDE047;">
                            ▲ API Degraded
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        except Exception:
            st.markdown(
                """
                <div style="text-align: right; padding-top: 8px;">
                    <span style="background: #FEE2E2; color: #991B1B; font-size: 0.82rem; font-weight: 600; padding: 5px 12px; border-radius: 16px; border: 1px solid #FCA5A5;">
                        ✕ API Offline
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("<hr style='margin-top: 4px; margin-bottom: 20px; border-color: #E2E8F0;'/>", unsafe_allow_html=True)
