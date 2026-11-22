"""Upload & Semantic Search Component for ClauseGuard."""

import streamlit as st
from frontend.api_client import ClauseGuardAPIClient, APIClientError


def render_pii_warning():
    """Renders prominent PII redaction compliance warning."""
    st.warning(
        """
        🔒 **Privacy Reminder — Redact Personal Information**

        Before uploading documents for live exhibition demonstrations, please ensure all sensitive Personally Identifiable Information (PII) has been removed or redacted:
        - Full names & family member details
        - Aadhaar numbers, PAN numbers, SSN, or national identity identifiers
        - Phone numbers & email addresses
        - Exact residential street addresses
        - Signatures & personal stamps
        - Bank account details, IBAN/SWIFT, or financial identifiers

        *ClauseGuard does not automatically anonymize uploaded files; please verify redaction before uploading.*
        """,
        icon="⚠️",
    )


def render_upload_and_search(api_client: ClauseGuardAPIClient):
    """Renders the document upload and semantic vector search interface."""
    st.subheader("📄 Document Upload & Semantic Retrieval")

    tab_upload, tab_search = st.tabs(["📤 Multipart Document Upload", "🔍 Semantic Clause Search"])

    # --------------------------------------------------------------------------
    # TAB 1: UPLOAD
    # --------------------------------------------------------------------------
    with tab_upload:
        render_pii_warning()

        st.markdown("Upload policy contracts, claim declarations, itemized bills, or supporting evidence.")

        col1, col2 = st.columns([2, 1])

        with col1:
            uploaded_file = st.file_uploader(
                "Choose document file",
                type=["pdf", "txt", "png", "jpg", "jpeg", "tiff"],
                help="PDF, text, and scanned image formats supported with OCR fallback.",
            )

        with col2:
            doc_type = st.selectbox(
                "Document Classification",
                options=[
                    "policy_document",
                    "claim_form",
                    "medical_invoice",
                    "discharge_summary",
                    "repair_estimate",
                    "photo_evidence",
                    "police_report",
                    "identity_proof",
                    "other",
                ],
                index=0,
                help="Select the appropriate document category to enable targeted clause partitioning.",
            )

            col_p, col_c = st.columns(2)
            with col_p:
                policy_id_input = st.number_input("Policy ID", min_value=1, value=1, step=1)
            with col_c:
                claim_id_input = st.number_input("Claim ID (optional)", min_value=0, value=1, step=1)

        upload_btn = st.button("⬆️ Ingest & Auto-Index Document", type="primary", disabled=uploaded_file is None)

        if upload_btn and uploaded_file:
            with st.spinner("Extracting clauses, persisting chunks, and indexing into ChromaDB..."):
                try:
                    file_bytes = uploaded_file.read()
                    claim_id_arg = claim_id_input if claim_id_input > 0 else None

                    res = api_client.upload_document(
                        file_bytes=file_bytes,
                        filename=uploaded_file.name,
                        document_type=doc_type,
                        policy_id=policy_id_input,
                        claim_id=claim_id_arg,
                    )

                    st.success(f"Document `{uploaded_file.name}` uploaded and processed successfully!")

                    # Show metadata cards
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Pages Extracted", res.get("page_count", 1))
                    c2.metric("Total Chunks", res.get("total_chunks", 0))
                    c3.metric("OCR Applied", "Yes" if res.get("ocr_applied") else "No")

                    indexed = res.get("indexed_in_vector_store", False)
                    idx_err = res.get("indexing_error")
                    if indexed:
                        c4.metric("ChromaDB Indexing", "Indexed ✓")
                    else:
                        c4.metric("ChromaDB Indexing", "Failed ⚠️")
                        st.warning(f"ChromaDB indexing warning: {idx_err}")

                except APIClientError as e:
                    st.error(f"Upload failed: {e}")
                except Exception as e:
                    st.error(f"Unexpected upload error: {str(e)}")

    # --------------------------------------------------------------------------
    # TAB 2: SEMANTIC SEARCH
    # --------------------------------------------------------------------------
    with tab_search:
        st.markdown(
            """
            Query the ChromaDB vector store (`clauseguard_policies` collection) using natural language.
            Retrieval uses dense semantic embeddings with strict policy and claim boundary filtering.
            """
        )

        col_q, col_k = st.columns([3, 1])
        with col_q:
            query = st.text_input(
                "Search query",
                placeholder="e.g. mandatory waiting period, room rent sub-limit, cosmetic surgery exclusion, lock-in period",
            )
        with col_k:
            top_k = st.slider("Top K Results", min_value=1, max_value=50, value=5, help="Bounded top_k (max 50).")

        with st.expander("Filter Options (Optional)", expanded=False):
            f_col1, f_col2, f_col3 = st.columns(3)
            with f_col1:
                filter_policy_id = st.number_input("Filter by Policy ID", min_value=0, value=0, step=1)
            with f_col2:
                filter_claim_id = st.number_input("Filter by Claim ID", min_value=0, value=0, step=1)
            with f_col3:
                filter_doc_type = st.selectbox(
                    "Filter by Document Type",
                    options=["(All Types)", "policy_document", "claim_form", "medical_invoice", "discharge_summary", "other"],
                    index=0,
                )

        search_btn = st.button("🔍 Search Document Chunks", type="primary", disabled=not query.strip())

        if search_btn and query.strip():
            with st.spinner("Generating query embeddings and querying ChromaDB..."):
                try:
                    p_id = filter_policy_id if filter_policy_id > 0 else None
                    c_id = filter_claim_id if filter_claim_id > 0 else None
                    d_type = filter_doc_type if filter_doc_type != "(All Types)" else None

                    res = api_client.search_documents(
                        query=query.strip(),
                        top_k=top_k,
                        policy_id=p_id,
                        claim_id=c_id,
                        document_type=d_type,
                    )

                    items = res.get("results", [])
                    st.markdown(f"**Found {len(items)} matching chunks:**")

                    if not items:
                        st.info("No matching chunks found for the given query and filters.")

                    for idx, item in enumerate(items, 1):
                        score = item.get("similarity_score")
                        score_label = f"Distance: {score:.4f}" if score is not None else "Distance: N/A"

                        title = f"#{idx} [{item.get('document_type', 'doc')}] {item.get('clause_or_section_ref') or 'General Section'}"
                        with st.expander(f"{title} — {score_label}", expanded=(idx <= 2)):
                            st.markdown(
                                f"""
                                <div style="font-size: 0.85rem; color: #64748B; margin-bottom: 8px;">
                                    <strong>Chunk ID:</strong> {item.get('chunk_id')} |
                                    <strong>Page:</strong> {item.get('page_number', 1)} |
                                    <strong>Policy ID:</strong> {item.get('policy_id')} |
                                    <strong>Claim ID:</strong> {item.get('claim_id') or 'N/A'}
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                            st.code(item.get("text", ""), language="text")

                    st.caption("ℹ️ Retrieval scores reflect dense embedding vector distance, not probability of fraud or legal certainty.")

                except APIClientError as e:
                    st.error(f"Search failed: {e}")
                except Exception as e:
                    st.error(f"Unexpected search error: {str(e)}")
