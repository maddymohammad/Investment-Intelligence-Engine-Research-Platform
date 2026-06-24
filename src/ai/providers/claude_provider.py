from __future__ import annotations

import logging
from typing import Optional

from .base import AIResponse, BaseAIProvider

logger = logging.getLogger(__name__)


class ClaudeProvider(BaseAIProvider):
    """Anthropic Claude implementation of BaseAIProvider."""

    def __init__(self) -> None:
        from config.settings import get_settings
        import anthropic

        settings = get_settings()
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")

        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._analysis_model = settings.claude_analysis_model
        self._screening_model = settings.claude_screening_model

    @property
    def name(self) -> str:
        return "claude"

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
            msg = self._client.messages.create(
                model=target_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_text,
                messages=[{"role": "user", "content": prompt}],
            )
            return AIResponse(
                content=msg.content[0].text,
                model=target_model,
                input_tokens=msg.usage.input_tokens,
                output_tokens=msg.usage.output_tokens,
            )
        except Exception as e:
            logger.error("Claude API error (model=%s): %s", target_model, e)
            raise
