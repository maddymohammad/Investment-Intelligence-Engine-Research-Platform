"""
Final stock selector: applies confidence threshold and returns 0-4 picks.

This is the ONLY place where the no-recommendation decision is made.
The rule is simple: if a stock does not exceed CONFIDENCE_THRESHOLD it is
dropped. We never inflate scores or lower thresholds to hit a pick count.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from src.analysis.composer import AnalysisResult
from src.selection import SelectionResult, StockCandidate
from src.selection.ranker import rank_candidates
from src.selection.screener import StockScreener

logger = logging.getLogger(__name__)


def select_stocks(
    analyses: dict[str, AnalysisResult],
    fundamentals: dict[str, dict],
    run_date: Optional[date] = None,
) -> SelectionResult:
    """
    Apply the full pipeline (screen → rank → threshold) and return a
    SelectionResult with 0–2 small cap and 0–2 large cap picks.

    Never forces a recommendation — returns empty lists when no stock
    clears the confidence threshold.
    """
    from config.settings import get_settings
    from datetime import date as _date

    settings = get_settings()
    rd = run_date or _date.today()
    threshold = settings.confidence_threshold
    screener = StockScreener(settings)

    result = SelectionResult()
    no_rec_reasons: list[str] = []

    for cap_cat, max_picks, attr in [
        ("SMALL", settings.max_small_cap_picks, "small_cap"),
        ("LARGE", settings.max_large_cap_picks, "large_cap"),
    ]:
        # Step 1: quality screen
        passed = screener.filter_by_cap(fundamentals, cap_cat)
        if not passed:
            msg = f"No {cap_cat} cap stocks passed minimum quality filters"
            no_rec_reasons.append(msg)
            logger.info(msg)
            continue

        # Step 2: rank top-10 from passed symbols
        cat_analyses = {s: analyses[s] for s in passed if s in analyses}
        if not cat_analyses:
            no_rec_reasons.append(f"No {cap_cat} cap stocks with complete analysis")
            continue

        ranked = rank_candidates(cat_analyses, cap_cat, top_n=10)

        # Step 3: confidence threshold gate
        picks: list[StockCandidate] = []
        for symbol, ar in ranked:
            if len(picks) >= max_picks:
                break

            confidence = ar.composite_score / 100.0
            if confidence < threshold:
                logger.info(
                    "%s (%s): score %.1f below threshold %.0f%% — NO PICK",
                    symbol, cap_cat, ar.composite_score, threshold * 100,
                )
                no_rec_reasons.append(
                    f"{cap_cat} {symbol}: score {ar.composite_score:.1f} < "
                    f"threshold {threshold*100:.0f}"
                )
                continue

            fund = fundamentals.get(symbol, {})
            entry_price = ar.current_price or fund.get("current_price") or 0.0

            picks.append(
                StockCandidate(
                    symbol=symbol,
                    name=fund.get("name") or symbol,
                    cap_category=cap_cat,
                    composite_score=ar.composite_score,
                    confidence_score=confidence,
                    fundamental_score=ar.fundamental_score,
                    technical_score=ar.technical_score,
                    sentiment_score=ar.sentiment_score,
                    entry_price=entry_price,
                    analysis_summary=(
                        f"F:{ar.fundamental_score:.0f} T:{ar.technical_score:.0f} "
                        f"V:{ar.valuation_score:.0f} R:{ar.risk_score:.0f} "
                        f"RSI:{ar.rsi or '—'} MACD:{ar.macd_signal or '—'}"
                    ),
                )
            )

        if not picks:
            no_rec_reasons.append(
                f"No {cap_cat} cap stock exceeded confidence threshold {threshold:.0%}"
            )
        else:
            setattr(result, attr, picks)
            logger.info("%s cap picks: %s", cap_cat, [p.symbol for p in picks])

    if not result.has_recommendations:
        result.no_recommendation_reason = "; ".join(no_rec_reasons) or (
            "No stocks met all criteria today"
        )
        logger.info("NO RECOMMENDATION today: %s", result.no_recommendation_reason)

    return result
