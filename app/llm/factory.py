"""LLM provider factory — singleton lifecycle management.

Switching providers is a config change, not a code change: set
``AI__LLM__PROVIDER=ollama|openai|azure_openai`` (or the matching key in
``config.yaml``) and restart. See docs/decisions for the rationale.
"""

from __future__ import annotations

import structlog

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.config import LLMSettings

logger = structlog.get_logger(__name__)

_llm: LLMProvider | None = None


def init_llm_provider(llm: LLMSettings, settings: Settings) -> LLMProvider:
    """Create and return a new LLM provider instance (pure factory, no singleton storage).

    Args:
        llm: LLM settings block (provider + per-provider config + call tuning).
        settings: Full application settings (for secrets).

    Raises:
        ValueError: Unknown provider or missing required credential.
    """
    match llm.provider:
        case "ollama":
            from app.llm.providers.ollama import OllamaLLM

            logger.info("llm.provider.initialized", provider="ollama", model=llm.ollama.model)
            return OllamaLLM(llm.ollama, llm)

        case "openai":
            if not settings.secrets.openai_api_key:
                raise ValueError("OPENAI_API_KEY must be set when ai.llm.provider=openai")
            from app.llm.providers.openai import OpenAILLM

            logger.info("llm.provider.initialized", provider="openai", model=llm.openai.model)
            return OpenAILLM(llm.openai, settings.secrets.openai_api_key, llm)

        case "azure_openai":
            if not settings.secrets.azure_openai_api_key:
                raise ValueError(
                    "AZURE_OPENAI_API_KEY must be set when ai.llm.provider=azure_openai"
                )
            if not llm.azure_openai.endpoint:
                raise ValueError("ai.llm.azure_openai.endpoint must be set")
            from app.llm.providers.azure_openai import AzureOpenAILLM

            logger.info(
                "llm.provider.initialized",
                provider="azure_openai",
                deployment=llm.azure_openai.deployment,
            )
            return AzureOpenAILLM(llm.azure_openai, settings.secrets.azure_openai_api_key, llm)

        case _:
            raise ValueError(f"Unsupported LLM provider: {llm.provider!r}")


def init_llm(settings: Settings) -> LLMProvider:
    """Initialize and store the process-wide LLM singleton. Call once at startup."""
    global _llm
    _llm = init_llm_provider(settings.ai.llm, settings)
    return _llm


def get_llm() -> LLMProvider:
    """Return the LLM provider singleton.

    Used by ``LLMDep`` in FastAPI dependency injection and by the worker.

    Raises:
        RuntimeError: If ``init_llm()`` has not been called.
    """
    if _llm is None:
        raise RuntimeError("LLM provider not initialized — call init_llm() at startup")
    return _llm
