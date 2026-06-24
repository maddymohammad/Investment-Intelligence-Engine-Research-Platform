from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class AIResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class BaseAIProvider(ABC):
    """
    All AI interactions go through this interface.
    Swap providers by setting AI_PROVIDER in the environment.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier, e.g. 'claude' or 'openai'."""

    @property
    @abstractmethod
    def analysis_model(self) -> str:
        """High-capability model used for deep stock analysis."""

    @property
    @abstractmethod
    def screening_model(self) -> str:
        """Fast/cheap model used for first-pass candidate screening."""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model: Optional[str] = None,
    ) -> AIResponse:
        """
        Send a single-turn prompt and return the response.

        Args:
            prompt: User message content.
            system: System instruction (defaults to generic analyst persona).
            max_tokens: Upper bound on response length.
            temperature: Sampling temperature (lower = more deterministic).
            model: Override the default model for this call only.
        """

    def complete_screening(self, prompt: str, **kwargs) -> AIResponse:
        """Convenience wrapper that forces the screening (cheap) model."""
        return self.complete(prompt, model=self.screening_model, **kwargs)

    def complete_analysis(self, prompt: str, **kwargs) -> AIResponse:
        """Convenience wrapper that forces the analysis (deep) model."""
        return self.complete(prompt, model=self.analysis_model, **kwargs)

    # Default system prompt shared across providers
    DEFAULT_SYSTEM = (
        "You are a senior investment analyst specialising in Indian equity markets "
        "(NSE/BSE). You reason from data, quantify uncertainty, and never fabricate "
        "numbers. When you lack data for a metric, say so explicitly."
    )
