from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StockCandidate:
    symbol: str
    name: str
    cap_category: str           # SMALL | LARGE
    composite_score: float      # 0–100
    confidence_score: float     # 0.0–1.0
    fundamental_score: float
    technical_score: float
    sentiment_score: float
    entry_price: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    analysis_summary: Optional[str] = None


@dataclass
class SelectionResult:
    """
    Container for a daily run's stock picks.
    Either list can be empty — never force a recommendation.
    """
    small_cap: list[StockCandidate] = field(default_factory=list)
    large_cap: list[StockCandidate] = field(default_factory=list)
    no_recommendation_reason: Optional[str] = None

    @property
    def has_recommendations(self) -> bool:
        return bool(self.small_cap or self.large_cap)

    @property
    def total_picks(self) -> int:
        return len(self.small_cap) + len(self.large_cap)

    @property
    def all_picks(self) -> list[StockCandidate]:
        return self.small_cap + self.large_cap
