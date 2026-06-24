from __future__ import annotations

import logging
from typing import Optional

from .base import AIResponse, BaseAIProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseAIProvider):
    """OpenAI implementation of BaseAIProvider."""

    def __init__(self) -> None:
        from config.settings import get_settings
        from openai import OpenAI

        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set")

        self._client = OpenAI(api_key=settings.openai_api_key)
        self._analysis_model = settings.openai_analysis_model
        self._screening_model = settings.openai_screening_model

    @property
    def name(self) -> str:
        return "openai"

    @property
    def analysis_model(self) -> str:
        return self._analysis_model

    @property
    def screening_model(self) -> str:
        return self._screening_model

    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> AIResponse:
        target_model = model or self._analysis_model
        system_text = system or self.DEFAULT_SYSTEM

        try:
            resp = self._client.chat.completions.create(
                model=target_model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_text},
                    {"role": "user", "content": prompt},
                ],
            )
            choice = resp.choices[0]
            return AIResponse(
                content=choice.message.content or "",
                model=target_model,
                input_tokens=resp.usage.prompt_tokens,
                output_tokens=resp.usage.completion_tokens,
            )
        except Exception as e:
            logger.error("OpenAI API error (model=%s): %s", target_model, e)
            raise
