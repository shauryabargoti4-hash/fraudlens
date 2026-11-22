"""Tests for ClauseGuard Frontend API Client."""

import pytest
from unittest.mock import patch, MagicMock
from frontend.api_client import ClauseGuardAPIClient, APIClientError


def test_api_client_initialization():
    client = ClauseGuardAPIClient(base_url="http://localhost:8000/api/v1/")
    assert client.base_url == "http://localhost:8000/api/v1"

    # Default environment fallback
    client_default = ClauseGuardAPIClient()
    assert "/api/v1" in client_default.base_url


def test_api_client_health_check_success():
    client = ClauseGuardAPIClient(base_url="http://test-server/api/v1")

    mock_resp = MagicMock()
    mock_resp.is_error = False
    mock_resp.json.return_value = {"status": "healthy", "version": "0.1.0"}

    with patch("httpx.Client.get", return_value=mock_resp):
        res = client.get_health()
        assert res["status"] == "healthy"
        assert client.is_connected() is True


def test_api_client_health_check_failure():
    client = ClauseGuardAPIClient(base_url="http://test-server/api/v1")

    with patch("httpx.Client.get", side_effect=Exception("Connection refused")):
        assert client.is_connected() is False
        with pytest.raises(APIClientError):
            client.get_health()


def test_api_client_search_documents():
    client = ClauseGuardAPIClient(base_url="http://test-server/api/v1")

    mock_resp = MagicMock()
    mock_resp.is_error = False
    mock_resp.json.return_value = {
        "query": "waiting period",
        "total_results": 1,
        "results": [{"chunk_id": 1, "text": "Waiting period rule", "similarity_score": 0.12}],
    }

    with patch("httpx.Client.post", return_value=mock_resp) as mock_post:
        res = client.search_documents(query="waiting period", top_k=5, policy_id=1)
        assert res["total_results"] == 1
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["query"] == "waiting period"
        assert call_kwargs["json"]["top_k"] == 5
        assert call_kwargs["json"]["policy_id"] == 1


def test_api_client_trigger_analysis():
    client = ClauseGuardAPIClient(base_url="http://test-server/api/v1")

    mock_resp = MagicMock()
    mock_resp.is_error = False
    mock_resp.json.return_value = {
        "claim_id": 1,
        "verdict": "DO_NOT_TAKE",
        "overall_risk_score": 100.0,
        "fallback_used": False,
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = client.trigger_claim_analysis(claim_id=1)
        assert res["verdict"] == "DO_NOT_TAKE"
        assert res["fallback_used"] is False


def test_api_client_handles_http_errors():
    client = ClauseGuardAPIClient(base_url="http://test-server/api/v1")

    mock_resp = MagicMock()
    mock_resp.is_error = True
    mock_resp.status_code = 404
    mock_resp.json.return_value = {"detail": "Claim not found"}

    with patch("httpx.Client.get", return_value=mock_resp):
        with pytest.raises(APIClientError) as exc_info:
            client.get_claim(999)
        assert exc_info.value.status_code == 404
        assert "Claim not found" in str(exc_info.value)
