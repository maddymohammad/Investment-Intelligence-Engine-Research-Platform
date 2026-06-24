from __future__ import annotations

import logging
from typing import Optional

from .providers.base import BaseAIProvider

logger = logging.getLogger(__name__)
_provider: Optional[BaseAIProvider] = None


def get_ai_provider() -> BaseAIProvider:
    """
    Return the singleton AI provider configured by AI_PROVIDER env var.
    Thread-safe for single-process use (GitHub Actions / cron).
    """
    global _provider
    if _provider is None:
        from config.settings import get_settings

        provider_name = get_settings().ai_provider.lower()

        if provider_name == "openai":
            from .providers.openai_provider import OpenAIProvider

            _provider = OpenAIProvider()
        else:
            from .providers.claude_provider import ClaudeProvider

            _provider = ClaudeProvider()

        logger.info("AI provider initialised: %s", _provider.name)

    return _provider


def reset_provider() -> None:
    """Force re-initialisation (useful in tests)."""
    global _provider
    _provider = None
