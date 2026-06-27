"""LLM provider factory."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.llm.base import LLMProvider
from app.llm.gemini import GeminiProvider, OpenAIProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    provider = get_settings().llm_provider.lower()
    if provider == "gemini":
        return GeminiProvider()
    if provider == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
