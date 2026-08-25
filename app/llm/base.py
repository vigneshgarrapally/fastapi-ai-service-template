"""LLM provider abstract base class and exception hierarchy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class LLMError(Exception):
    """Base for all LLM provider errors."""


class LLMRateLimitError(LLMError):
    """HTTP 429 — retryable. May carry provider-supplied retry_after seconds."""

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class LLMServiceUnavailableError(LLMError):
    """HTTP 5xx / connection error / timeout — retryable."""


class LLMAuthError(LLMError):
    """HTTP 401/403 / bad request — not retryable."""


class LLMContextLengthError(LLMError):
    """Input exceeds model context limit — not retryable."""


class LLMProvider(ABC):
    """Abstract interface every LLM backend must implement."""

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, Any]],
        response_format: type[BaseModel] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str | BaseModel:
        """Send messages to the model and return a response.

        Args:
            messages: OpenAI-style list of role/content dicts.
            response_format: Optional Pydantic model for structured output. When
                provided, the return value is a validated instance of this model.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens. Provider default when None.

        Returns:
            A string (unstructured) or a validated Pydantic model instance (structured).

        Raises:
            LLMRateLimitError: HTTP 429.
            LLMServiceUnavailableError: 5xx / connection / timeout.
            LLMAuthError: 401/403 / bad request.
            LLMContextLengthError: Input exceeds context limit.
        """
