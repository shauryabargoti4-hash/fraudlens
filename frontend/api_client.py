"""ClauseGuard API Client.

Interfaces with the FastAPI backend REST API. Supports configurable base URL
via CLAUSEGUARD_API_URL, RBAC role-switching headers, and provides robust error handling.
"""

import os
from typing import Any, Dict, List, Optional
import httpx


class APIClientError(Exception):
    """Raised when an API operation fails."""

    def __init__(self, message: str, status_code: Optional[int] = None, detail: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class ClauseGuardAPIClient:
    """Client for communicating with ClauseGuard FastAPI backend."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        role: str = "AUDITOR",
        operator_name: str = "Staff Claims Auditor",
    ):
        raw_url = base_url or os.getenv("CLAUSEGUARD_API_URL", "http://127.0.0.1:8000/api/v1")
        self.base_url = raw_url.rstrip("/")
        self.timeout = timeout
        self.role = role
        self.operator_name = operator_name

    def _headers(self) -> Dict[str, str]:
        """Provides lightweight RBAC headers."""
        return {
            "X-User-Role": self.role,
            "X-User-Name": self.operator_name,
        }

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, params=params, headers=self._headers())
                if res.is_error:
                    detail = None
                    try:
                        detail = res.json().get("detail")
                    except Exception:
                        detail = res.text
                    raise APIClientError(
                        f"GET {path} failed with HTTP {res.status_code}: {detail}",
                        status_code=res.status_code,
                        detail=detail,
                    )
                return res.json()
        except APIClientError:
            raise
        except (httpx.RequestError, Exception) as exc:
            raise APIClientError(f"Connection to backend at {url} failed: {str(exc)}")

    def _get_bytes(self, path: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, params=params, headers=self._headers())
                if res.is_error:
                    detail = None
                    try:
                        detail = res.json().get("detail")
                    except Exception:
                        detail = res.text
                    raise APIClientError(
                        f"GET {path} failed with HTTP {res.status_code}: {detail}",
                        status_code=res.status_code,
                        detail=detail,
                    )
                return res.content
        except APIClientError:
            raise
        except (httpx.RequestError, Exception) as exc:
            raise APIClientError(f"Connection to backend at {url} failed: {str(exc)}")

    def _post(
        self,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=json_data, files=files, data=data, headers=self._headers())
                if res.is_error:
                    detail = None
                    try:
                        detail = res.json().get("detail")
                    except Exception:
                        detail = res.text
                    raise APIClientError(
                        f"POST {path} failed with HTTP {res.status_code}: {detail}",
                        status_code=res.status_code,
                        detail=detail,
                    )
                return res.json()
        except APIClientError:
            raise
        except (httpx.RequestError, Exception) as exc:
            raise APIClientError(f"Connection to backend at {url} failed: {str(exc)}")

    # --------------------------------------------------------------------------
    # Health & System Probes
    # --------------------------------------------------------------------------
    def get_health(self) -> Dict[str, Any]:
        """Probes /health endpoint for quick connectivity check."""
        return self._get("/health")

    def get_system_status(self) -> Dict[str, Any]:
        """Fetches detailed system status including database, storage, and AI models."""
        return self._get("/system/status")

    def is_connected(self) -> bool:
        """Returns True if the backend is reachable and healthy."""
        try:
            res = self.get_health()
            return res.get("status") == "healthy"
        except Exception:
            return False

    # --------------------------------------------------------------------------
    # Policies & Claims
    # --------------------------------------------------------------------------
    def list_policies(self, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists active insurance policies."""
        return self._get("/policies", params={"skip": skip, "limit": limit})

    def list_claims(self, skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists claims registered in the system."""
        return self._get("/claims", params={"skip": skip, "limit": limit})

    def get_claim(self, claim_id: int) -> Dict[str, Any]:
        """Fetches single claim record."""
        return self._get(f"/claims/{claim_id}")

    # --------------------------------------------------------------------------
    # Analysis Workflow & Reports
    # --------------------------------------------------------------------------
    def trigger_claim_analysis(self, claim_id: int) -> Dict[str, Any]:
        """Triggers the full LangGraph review workflow for a claim."""
        return self._post(f"/claims/{claim_id}/analyze")

    def get_latest_claim_analysis(self, claim_id: int) -> Dict[str, Any]:
        """Fetches the latest persisted analysis report for a claim."""
        return self._get(f"/claims/{claim_id}/analysis")

    # --------------------------------------------------------------------------
    # Batch Claim Portfolio Audit (Wave 5)
    # --------------------------------------------------------------------------
    def batch_audit_claims(
        self,
        claim_ids: Optional[List[int]] = None,
        policy_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Executes portfolio-wide batch audit across multiple claims with error isolation."""
        payload: Dict[str, Any] = {}
        if claim_ids is not None:
            payload["claim_ids"] = claim_ids
        if policy_id is not None:
            payload["policy_id"] = policy_id
        return self._post("/claims/batch-audit", json_data=payload)

    # --------------------------------------------------------------------------
    # Executive PDF Audit Report Export (Wave 5)
    # --------------------------------------------------------------------------
    def export_report_pdf(self, report_id: int) -> bytes:
        """Downloads publication-ready PDF bytes for a specific report ID."""
        return self._get_bytes(f"/reports/{report_id}/export/pdf")

    def export_claim_report_pdf(self, claim_id: int) -> bytes:
        """Downloads publication-ready PDF bytes for the latest claim report."""
        return self._get_bytes(f"/reports/claim/{claim_id}/export/pdf")

    # --------------------------------------------------------------------------
    # Adjudicator Digital Sign-Off & Verdict Override (Wave 5 RBAC)
    # --------------------------------------------------------------------------
    def override_report_verdict(
        self,
        report_id: int,
        final_verdict: str,
        adjudicator_name: str,
        justification: str,
    ) -> Dict[str, Any]:
        """Records senior adjudicator verdict override and writes to audit log."""
        payload = {
            "final_verdict": final_verdict,
            "adjudicator_name": adjudicator_name,
            "justification": justification,
        }
        return self._post(f"/reports/{report_id}/override", json_data=payload)

    # --------------------------------------------------------------------------
    # Document Upload & Semantic Search
    # --------------------------------------------------------------------------
    def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        document_type: str,
        policy_id: Optional[int] = None,
        claim_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Uploads and auto-indexes a document."""
        files = {"file": (filename, file_bytes, "application/octet-stream")}
        data: Dict[str, Any] = {"document_type": document_type}
        if policy_id is not None:
            data["policy_id"] = str(policy_id)
        if claim_id is not None:
            data["claim_id"] = str(claim_id)
        return self._post("/documents/upload", files=files, data=data)

    def search_documents(
        self,
        query: str,
        top_k: int = 10,
        policy_id: Optional[int] = None,
        claim_id: Optional[int] = None,
        document_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Performs semantic vector search against ChromaDB."""
        payload: Dict[str, Any] = {
            "query": query,
            "top_k": top_k,
        }
        if policy_id is not None:
            payload["policy_id"] = policy_id
        if claim_id is not None:
            payload["claim_id"] = claim_id
        if document_type:
            payload["document_type"] = document_type
        return self._post("/documents/search", json_data=payload)

    # --------------------------------------------------------------------------
    # Exhibition Showcase & Demo Reset (Wave 6)
    # --------------------------------------------------------------------------
    def reset_demo_state(self) -> Dict[str, Any]:
        """Safely resets demo test state back to baseline sample state without data loss."""
        return self._post("/system/reset-demo")
