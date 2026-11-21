from unittest.mock import MagicMock, patch
import pytest
from pydantic import BaseModel, Field
from backend.services.llm_provider import (
    BaseLLMProvider,
    GeminiLLMProvider,
    MockLLMProvider,
    LLMResponse,
    get_llm_provider,
)


class SampleClaimExtraction(BaseModel):
    claimant_name: str
    incident_date: str
    claimed_amount: float
    is_emergency: bool = False


def test_mock_provider_text_generation():
    provider = MockLLMProvider(default_text="Audit completed successfully.")
    res = provider.generate_text(prompt="Assess claim CLM-8801")
    assert res.success is True
    assert "Audit completed successfully" in res.text
    assert res.fallback_used is False
    assert res.model_used == "mock-gemini-model"


def test_mock_provider_structured_generation():
    provider = MockLLMProvider()
    res = provider.generate_structured(
        prompt="Extract claim details",
        response_schema=SampleClaimExtraction,
    )
    assert res.success is True
    assert res.structured_data is not None
    assert isinstance(res.structured_data, SampleClaimExtraction)
    assert res.structured_data.claimant_name == "Mock claimant_name"
    assert res.structured_data.claimed_amount == 0.85


def test_mock_provider_simulated_primary_fallback():
    provider = MockLLMProvider(simulate_primary_failure=True)
    res = provider.generate_text("Analyze clause")
    assert res.success is True
    assert res.fallback_used is True
    assert res.model_used == "mock-gemini-fallback"
    assert "quota" in (res.fallback_reason or "").lower()


def test_mock_provider_simulated_complete_failure():
    provider = MockLLMProvider(simulate_failure=True)
    res = provider.generate_text("Prompt")
    assert res.success is False
    assert res.error == "Simulated provider failure"


def test_gemini_provider_missing_api_key_graceful():
    provider = GeminiLLMProvider(api_key="")
    res = provider.generate_text("Analyze policy")
    assert res.success is False
    assert "GEMINI_API_KEY is not configured" in (res.error or "")


def test_gemini_provider_successful_primary_call():
    provider = GeminiLLMProvider(api_key="test-api-key")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "This policy covers inpatient bed charges up to $500/day."
    mock_client.models.generate_content.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_client):
        res = provider.generate_text(prompt="Summarize room limit")
        assert res.success is True
        assert res.fallback_used is False
        assert "inpatient bed charges" in res.text
        assert res.model_used == provider.primary_model


def test_gemini_provider_recoverable_error_triggers_fallback():
    provider = GeminiLLMProvider(
        api_key="test-api-key",
        primary_model="gemini-1.5-pro",
        fallback_model="gemini-1.5-flash",
    )

    mock_client = MagicMock()

    # Primary model throws 429 quota exhausted; fallback succeeds
    def mock_generate_content(model, contents, config):
        if model == "gemini-1.5-pro":
            raise RuntimeError("429 Resource Exhausted: Model is overloaded.")
        mock_resp = MagicMock()
        mock_resp.text = "Fallback response from flash model."
        return mock_resp

    mock_client.models.generate_content.side_effect = mock_generate_content

    with patch.object(provider, "_get_client", return_value=mock_client):
        res = provider.generate_text(prompt="Evaluate claim")
        assert res.success is True
        assert res.fallback_used is True
        assert res.model_used == "gemini-1.5-flash"
        assert "429 Resource Exhausted" in (res.fallback_reason or "")
        assert "Fallback response" in res.text


def test_gemini_provider_non_recoverable_error_fails_immediately():
    provider = GeminiLLMProvider(api_key="test-api-key")

    mock_client = MagicMock()
    # Non-recoverable error (e.g. invalid argument / authentication rejected)
    mock_client.models.generate_content.side_effect = ValueError("Invalid authentication credentials")

    with patch.object(provider, "_get_client", return_value=mock_client):
        res = provider.generate_text(prompt="Evaluate claim")
        assert res.success is False
        assert res.fallback_used is False
        assert "Non-recoverable" in (res.error or "")


def test_gemini_provider_both_primary_and_fallback_fail():
    provider = GeminiLLMProvider(api_key="test-api-key")

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("503 Service Unavailable")

    with patch.object(provider, "_get_client", return_value=mock_client):
        res = provider.generate_text(prompt="Evaluate claim")
        assert res.success is False
        assert res.fallback_used is True
        assert "Primary failed" in (res.error or "")
        assert "Fallback failed" in (res.error or "")


def test_gemini_provider_structured_output_success():
    provider = GeminiLLMProvider(api_key="test-api-key")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"claimant_name": "David Vance", "incident_date": "2026-02-15", "claimed_amount": 9570.0, "is_emergency": false}'
    mock_client.models.generate_content.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_client):
        res = provider.generate_structured(
            prompt="Extract claim information",
            response_schema=SampleClaimExtraction,
        )
        assert res.success is True
        assert isinstance(res.structured_data, SampleClaimExtraction)
        assert res.structured_data.claimant_name == "David Vance"
        assert res.structured_data.claimed_amount == 9570.0


def test_gemini_provider_structured_output_invalid_json():
    provider = GeminiLLMProvider(api_key="test-api-key")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"claimant_name": "David Vance", INVALID_JSON...'
    mock_client.models.generate_content.return_value = mock_response

    with patch.object(provider, "_get_client", return_value=mock_client):
        res = provider.generate_structured(
            prompt="Extract claim information",
            response_schema=SampleClaimExtraction,
        )
        assert res.success is False
        assert "Schema validation error" in (res.error or "")


def test_get_llm_provider_factory():
    # Factory with mock
    mock_prov = get_llm_provider("mock")
    assert isinstance(mock_prov, MockLLMProvider)

    # Factory with gemini and mock api key
    gem_prov = get_llm_provider("gemini", api_key="test-key")
    assert isinstance(gem_prov, GeminiLLMProvider)
