"""Gemini LLM Provider and Model Management for ClauseGuard.

Provides a unified interface for text and structured generation using the official
Google Gen AI SDK (`google-genai`), featuring controlled fallback, timeout handling,
and deterministic mocking for test suites.
"""

from abc import ABC, abstractmethod
import json
from typing import Any, Optional, Type, TypeVar
from pydantic import BaseModel, Field
from backend.core.config import get_settings, Settings
from backend.core.logging_config import logger

T = TypeVar("T", bound=BaseModel)


class LLMResponse(BaseModel):
    """Structured response container for all LLM generation calls."""

    text: str = Field("", description="Raw generated text from the model")
    model_used: str = Field("", description="Actual model that generated the response")
    fallback_used: bool = Field(False, description="Whether fallback model was invoked")
    fallback_reason: Optional[str] = Field(None, description="Reason fallback was triggered")
    success: bool = Field(True, description="Whether generation succeeded")
    error: Optional[str] = Field(None, description="Error message if generation failed")
    structured_data: Optional[Any] = Field(None, description="Validated Pydantic model instance if structured")
    raw_metadata: dict = Field(default_factory=dict, description="Token usage, finish reasons, etc.")


class BaseLLMProvider(ABC):
    """Abstract contract for LLM generation in ClauseGuard."""

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Generate unstructured text."""
        pass

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Generate structured JSON conforming to a Pydantic schema."""
        pass


class GeminiLLMProvider(BaseLLMProvider):
    """Official Google Gen AI SDK (`google-genai`) LLM provider with primary -> fallback orchestration."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.api_key = api_key or self.settings.gemini_api_key
        self.primary_model = primary_model or self.settings.gemini_model
        self.fallback_model = fallback_model or self.settings.gemini_fallback_model
        self.temperature = temperature if temperature is not None else self.settings.gemini_temperature
        self.max_output_tokens = max_output_tokens or self.settings.gemini_max_output_tokens
        self.timeout_seconds = timeout_seconds or self.settings.gemini_timeout_seconds

        self._client = None
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Google Gen AI client: {e}")

    def _get_client(self):
        if not self._client:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY is not configured or provided.")
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _is_recoverable_error(self, error: Exception) -> bool:
        """Determines if an API error is transient/recoverable, justifying fallback."""
        err_msg = str(error).lower()
        recoverable_terms = [
            "429", "quota", "rate limit", "resource exhausted",
            "500", "503", "unavailable", "overloaded",
            "timeout", "timed out", "deadline", "connection",
            "model not found", "not supported for this model",
        ]
        return any(term in err_msg for term in recoverable_terms)

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> LLMResponse:
        temp = temperature if temperature is not None else self.temperature
        max_tokens = max_output_tokens or self.max_output_tokens

        try:
            client = self._get_client()
        except Exception as e:
            return LLMResponse(
                success=False,
                error=f"Client initialization error: {e}",
                model_used=self.primary_model,
            )

        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=temp,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
        )

        # 1. Attempt primary model
        try:
            response = client.models.generate_content(
                model=self.primary_model,
                contents=prompt,
                config=config,
            )
            return LLMResponse(
                text=response.text or "",
                model_used=self.primary_model,
                fallback_used=False,
                success=True,
            )
        except Exception as primary_err:
            logger.warning(f"Primary model '{self.primary_model}' invocation failed: {primary_err}")

            if not self._is_recoverable_error(primary_err):
                # Non-recoverable error (e.g. invalid auth, bad request) -> fail fast
                return LLMResponse(
                    success=False,
                    error=f"Non-recoverable primary model error: {primary_err}",
                    model_used=self.primary_model,
                    fallback_used=False,
                )

            # 2. Attempt fallback model
            logger.info(f"Attempting fallback model '{self.fallback_model}'...")
            try:
                response = client.models.generate_content(
                    model=self.fallback_model,
                    contents=prompt,
                    config=config,
                )
                return LLMResponse(
                    text=response.text or "",
                    model_used=self.fallback_model,
                    fallback_used=True,
                    fallback_reason=str(primary_err),
                    success=True,
                )
            except Exception as fallback_err:
                logger.error(f"Fallback model '{self.fallback_model}' also failed: {fallback_err}")
                return LLMResponse(
                    success=False,
                    error=f"Primary failed ({primary_err}); Fallback failed ({fallback_err})",
                    model_used=self.fallback_model,
                    fallback_used=True,
                    fallback_reason=str(primary_err),
                )

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        temp = temperature if temperature is not None else self.temperature

        try:
            client = self._get_client()
        except Exception as e:
            return LLMResponse(
                success=False,
                error=f"Client initialization error: {e}",
                model_used=self.primary_model,
            )

        from google.genai import types

        config = types.GenerateContentConfig(
            temperature=temp,
            max_output_tokens=self.max_output_tokens,
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=response_schema,
        )

        def _execute_model(model_name: str) -> str:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            return resp.text or ""

        # 1. Primary Model
        model_used = self.primary_model
        fallback_used = False
        fallback_reason = None
        raw_text = ""

        try:
            raw_text = _execute_model(self.primary_model)
        except Exception as primary_err:
            logger.warning(f"Primary model '{self.primary_model}' structured generation failed: {primary_err}")
            if not self._is_recoverable_error(primary_err):
                return LLMResponse(
                    success=False,
                    error=f"Primary model failure: {primary_err}",
                    model_used=self.primary_model,
                )
            # Attempt fallback model
            try:
                raw_text = _execute_model(self.fallback_model)
                model_used = self.fallback_model
                fallback_used = True
                fallback_reason = str(primary_err)
            except Exception as fallback_err:
                return LLMResponse(
                    success=False,
                    error=f"Primary failed ({primary_err}); Fallback failed ({fallback_err})",
                    model_used=self.fallback_model,
                    fallback_used=True,
                    fallback_reason=str(primary_err),
                )

        # 2. Parse and Validate Schema
        try:
            validated = response_schema.model_validate_json(raw_text)
            return LLMResponse(
                text=raw_text,
                model_used=model_used,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                success=True,
                structured_data=validated,
            )
        except Exception as parse_err:
            logger.error(f"Failed to validate response against schema {response_schema.__name__}: {parse_err}")
            return LLMResponse(
                text=raw_text,
                model_used=model_used,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                success=False,
                error=f"Schema validation error: {parse_err}",
            )


class MockLLMProvider(BaseLLMProvider):
    """Deterministic, offline mock provider for testing and environments without Gemini credentials."""

    def __init__(
        self,
        default_text: str = "Mock generation response for ClauseGuard.",
        simulate_failure: bool = False,
        simulate_primary_failure: bool = False,
        model_name: str = "mock-gemini-model",
        fallback_model_name: str = "mock-gemini-fallback",
    ):
        self.default_text = default_text
        self.simulate_failure = simulate_failure
        self.simulate_primary_failure = simulate_primary_failure
        self.model_name = model_name
        self.fallback_model_name = fallback_model_name

    def generate_text(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> LLMResponse:
        if self.simulate_failure:
            return LLMResponse(
                success=False,
                error="Simulated provider failure",
                model_used=self.model_name,
            )

        if self.simulate_primary_failure:
            return LLMResponse(
                text=self.default_text,
                model_used=self.fallback_model_name,
                fallback_used=True,
                fallback_reason="Simulated primary model 429 quota exhaustion",
                success=True,
            )

        return LLMResponse(
            text=f"{self.default_text} (Prompt echo: {prompt[:30]}...)",
            model_used=self.model_name,
            fallback_used=False,
            success=True,
        )

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        if self.simulate_failure:
            return LLMResponse(
                success=False,
                error="Simulated structured provider failure",
                model_used=self.model_name,
            )

        # Build mock valid dictionary matching schema fields
        mock_data = {}
        for field_name, field_info in response_schema.model_fields.items():
            annotation = field_info.annotation
            if annotation == str or str in getattr(annotation, "__args__", ()):
                mock_data[field_name] = f"Mock {field_name}"
            elif annotation == int or int in getattr(annotation, "__args__", ()):
                mock_data[field_name] = 1
            elif annotation == float or float in getattr(annotation, "__args__", ()):
                mock_data[field_name] = 0.85
            elif annotation == bool or bool in getattr(annotation, "__args__", ()):
                mock_data[field_name] = True
            elif annotation == list or getattr(annotation, "__origin__", None) == list:
                mock_data[field_name] = []
            else:
                mock_data[field_name] = None

        try:
            validated = response_schema.model_validate(mock_data)
            json_str = validated.model_dump_json()

            if self.simulate_primary_failure:
                return LLMResponse(
                    text=json_str,
                    model_used=self.fallback_model_name,
                    fallback_used=True,
                    fallback_reason="Simulated primary model timeout",
                    success=True,
                    structured_data=validated,
                )

            return LLMResponse(
                text=json_str,
                model_used=self.model_name,
                fallback_used=False,
                success=True,
                structured_data=validated,
            )
        except Exception as e:
            return LLMResponse(
                success=False,
                error=f"Mock schema generation error: {e}",
                model_used=self.model_name,
            )


def get_llm_provider(
    provider_type: Optional[str] = None,
    api_key: Optional[str] = None,
) -> BaseLLMProvider:
    """Factory returns configured LLM provider (Gemini or Mock)."""
    settings = get_settings()
    selected = (provider_type or settings.llm_provider).lower()

    if selected == "mock" or not (api_key or settings.gemini_api_key):
        # Default to Mock when explicitly requested or when no API key is provided
        return MockLLMProvider()

    return GeminiLLMProvider(api_key=api_key)
