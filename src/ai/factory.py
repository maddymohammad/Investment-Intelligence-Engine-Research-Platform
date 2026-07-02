from __future__ import annotations

import logging
from typing import Optional

from .providers.base import BaseAIProvider

logger = logging.getLogger(__name__)
_provider: Optional[BaseAIProvider] = None


def is_ai_configured() -> bool:
    """
    True when the configured AI provider has an API key available.

    Used by the analyst layer to decide between AI narratives and the
    free rule-based quant narratives — WITHOUT instantiating a provider
    (instantiation raises when the key is missing).
    """
    from config.settings import get_settings

    settings = get_settings()
    name = settings.ai_provider.lower()
    if name == "openai":
        return bool(settings.openai_api_key)
    # "claude" / "anthropic" / anything else defaults to the Claude provider
    return bool(settings.anthropic_api_key)


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
