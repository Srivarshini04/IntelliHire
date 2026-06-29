"""Gemini LLM provider — default for DELULU."""

from __future__ import annotations

import json
import logging
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class GeminiProvider:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._model = self._settings.gemini_model

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_json(
        self,
        prompt: str,
        schema: type[T],
        *,
        system: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        raw = await self.generate_text(prompt, system=system, temperature=temperature)
        try:
            data = json.loads(raw)
            return schema.model_validate(data)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Gemini JSON parse failed: %s", exc)
            raise ValueError(f"LLM returned invalid JSON for {schema.__name__}") from exc

    async def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.1,
    ) -> str:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            self._model,
            system_instruction=system,
        )
        response = model.generate_content(
            prompt,
            generation_config={"temperature": temperature, "response_mime_type": "application/json"},
        )
        return response.text or ""


class OpenAIProvider:
    """Stub — swap provider via LLM_PROVIDER=openai without touching engines."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._model = self._settings.openai_model

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_json(self, prompt: str, schema: type[T], **kwargs) -> T:
        raise NotImplementedError("OpenAI provider not yet implemented — set LLM_PROVIDER=gemini")

    async def generate_text(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError("OpenAI provider not yet implemented — set LLM_PROVIDER=gemini")
