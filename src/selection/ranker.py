"""
Ranks screened candidates by composite score and applies sector rotation bonus.
Returns an ordered list ready for the confidence-threshold selector.
"""
from __future__ import annotations

import logging
from typing import Optional

from src.analysis.composer import AnalysisResult

logger = logging.getLogger(__name__)


def rank_candidates(
    analyses: dict[str, AnalysisResult],
    cap_category: str,
    top_n: int = 10,
) -> list[tuple[str, AnalysisResult]]:
    """
    Filter to `cap_category` stocks, sort by composite_score descending,
    return at most top_n as [(symbol, AnalysisResult)].
    """
    from src.storage.db import get_session
    from src.storage.models import Stock

    # Determine which symbols belong to the requested cap category
    # Use the cap_category stored on the AnalysisResult's sector field
    # (populated from yfinance info via FundamentalCollector → UniverseManager)
    # We look it up from the DB for accuracy; fall back to fundamentals dict.
    def _get_cap(symbol: str) -> Optional[str]:
        try:
            with get_session() as session:
                stock = session.query(Stock).filter_by(symbol=symbol).first()
                return stock.cap_category if stock else None
        except Exception:
            return None

    ranked: list[tuple[str, AnalysisResult]] = []
    for symbol, result in analyses.items():
        cat = _get_cap(symbol)
        if cat != cap_category:
            continue
        ranked.append((symbol, result))

    ranked.sort(key=lambda x: x[1].composite_score, reverse=True)
    top = ranked[:top_n]

    if top:
        logger.info(
            "%s cap candidates (top %d): %s",
            cap_category,
            len(top),
            ", ".join(f"{s}={r.composite_score:.1f}" for s, r in top[:5]),
        )
    return top
