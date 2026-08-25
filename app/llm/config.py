"""LLM provider configuration models."""

from typing import Literal

from pydantic import BaseModel, Field


class OllamaLLMConfig(BaseModel):
    base_url: str = "http://localhost:11434/v1"
    model: str = "llama3.1"


class OpenAILLMConfig(BaseModel):
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"


class AzureOpenAILLMConfig(BaseModel):
    endpoint: str = ""
    deployment: str = "gpt-4o"
    api_version: str = "2024-02-01"


class LLMSettings(BaseModel):
    provider: Literal["ollama", "openai", "azure_openai"] = "azure_openai"
    ollama: OllamaLLMConfig = OllamaLLMConfig()
    openai: OpenAILLMConfig = OpenAILLMConfig()
    azure_openai: AzureOpenAILLMConfig = AzureOpenAILLMConfig()
    timeout_s: int = Field(default=30, gt=0)
    max_retries: int = Field(default=4, ge=0)
    max_tokens: int = Field(default=4000, gt=0)
