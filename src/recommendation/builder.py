"""
Pre-populates the quantitative fields of each recommendation section
from already-computed data before the AI layer fills in the narratives.

Phase 3 (AI analyst) calls build_pre_ai_recommendation() to get a
partially-filled StockRecommendation, then completes the narrative
fields via Claude/OpenAI.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from src.analysis.composer import AnalysisResult
from src.recommendation import (
    ConfidenceDetail,
    FundamentalSummary,
    InvestmentHorizon,
    NewsCatalysts,
    ResearchGuidance,
    RiskAnalysis,
    SelectionJustification,
    StockRecommendation,
    TechnicalSummary,
)

logger = logging.getLogger(__name__)


def build_technical_section(
    ar: AnalysisResult,
    support_levels: Optional[list[float]] = None,
    resistance_levels: Optional[list[float]] = None,
) -> TechnicalSummary:
    signals = ar.technical_signals

    return TechnicalSummary(
        rsi=ar.rsi,
        rsi_interpretation=_interpret_rsi(ar.rsi),
        macd_status=ar.macd_signal or "NEUTRAL",
        # narrative filled by AI
        sma_20=signals.get("sma_20"),
        sma_50=signals.get("sma_50"),
        sma_200=signals.get("sma_200"),
        support_levels=support_levels or [],
        resistance_levels=resistance_levels or [],
        volume_ratio_5d_vs_20d=signals.get("volume_ratio_5d_vs_20d"),
        adx=signals.get("adx"),
        overall_technical_signal=_overall_signal(ar.technical_score),
    )


def build_fundamental_section(
    fund_data: dict,
    sector_performance: Optional[dict] = None,
) -> FundamentalSummary:
    sector = fund_data.get("sector")
    rs = None
    if sector and sector_performance:
        from src.analysis.sector import get_sector_relative_strength
        rs = get_sector_relative_strength(sector, sector_performance)

    roe = fund_data.get("roe")
    roce = fund_data.get("roce")
    pm = fund_data.get("profit_margin")
    om = fund_data.get("operating_margin")
    rg = fund_data.get("revenue_growth")
    eg = fund_data.get("earnings_growth")

    return FundamentalSummary(
        revenue_growth_pct=_pct(rg),
        eps_growth_pct=_pct(eg),
        roe_pct=_pct(roe),
        roce_pct=roce if (roce and roce > 1.5) else _pct(roce),
        debt_to_equity=fund_data.get("debt_to_equity"),
        profit_margin_pct=_pct(pm),
        operating_margin_pct=_pct(om),
        pe_ratio=fund_data.get("pe_ratio"),
        peg_ratio=fund_data.get("peg_ratio"),
        pb_ratio=fund_data.get("price_to_book"),
        free_cashflow=fund_data.get("free_cashflow"),
        sector=sector,
        sector_relative_strength_pct=rs,
        # narratives left for AI
    )


def build_risk_section(ar: AnalysisResult) -> RiskAnalysis:
    return RiskAnalysis(
        beta=ar.beta,
        volatility_annual_pct=ar.volatility_annual_pct,
        max_drawdown_pct=ar.max_drawdown_pct,
        # narratives (bear_case, sector_risks, etc.) left for AI
    )


def build_pre_ai_recommendation(
    ar: AnalysisResult,
    fund_data: dict,
    news_headlines: Optional[list[str]] = None,
    sector_performance: Optional[dict] = None,
    support_levels: Optional[list[float]] = None,
    resistance_levels: Optional[list[float]] = None,
    run_date: Optional[date] = None,
) -> StockRecommendation:
    """
    Returns a StockRecommendation with all quantitative fields populated.
    Narrative text fields are empty strings — the AI layer fills them.
    """
    from datetime import date as _date
    rd = run_date or _date.today()

    rec = StockRecommendation(
        symbol=ar.symbol,
        name=fund_data.get("name") or ar.symbol,
        cap_category=fund_data.get("cap_category", "LARGE"),
        run_date=rd,
        composite_score=ar.composite_score,
        confidence_score=ar.composite_score / 100.0,
        fundamental_score=ar.fundamental_score,
        technical_score=ar.technical_score,
        valuation_score=ar.valuation_score,
        risk_score=ar.risk_score,
        entry_price=ar.current_price or fund_data.get("current_price") or 0.0,
    )

    rec.technical = build_technical_section(ar, support_levels, resistance_levels)
    rec.fundamental = build_fundamental_section(fund_data, sector_performance)
    rec.risk = build_risk_section(ar)

    # Seed catalysts with news headlines; AI will categorise them
    rec.catalysts = NewsCatalysts(
        macro_factors=news_headlines or [],
    )

    # Confidence: quantitative score pre-set; explanation left for AI
    rec.confidence = ConfidenceDetail(
        score=ar.composite_score,
    )

    # Placeholders for AI sections
    rec.horizon = InvestmentHorizon()
    rec.justification = SelectionJustification()
    rec.guidance = ResearchGuidance()

    return rec


# ─── Private helpers ──────────────────────────────────────────────────────────

def _pct(v: Optional[float]) -> Optional[float]:
    """Convert a yfinance decimal (0.18) to percentage (18.0), rounded."""
    if v is None:
        return None
    val = v * 100 if abs(v) <= 1.5 else v  # already a % if > 1.5
    return round(val, 2)


def _interpret_rsi(rsi: Optional[float]) -> str:
    if rsi is None:
        return "Data unavailable"
    if rsi < 30:
        return f"Oversold ({rsi:.1f}) — potential mean-reversion opportunity"
    if rsi < 40:
        return f"Near oversold ({rsi:.1f}) — weakening momentum"
    if rsi < 60:
        return f"Neutral ({rsi:.1f}) — no extreme reading"
    if rsi < 70:
        return f"Approaching overbought ({rsi:.1f}) — momentum strong but watch for reversal"
    return f"Overbought ({rsi:.1f}) — caution on near-term upside"


def _overall_signal(tech_score: float) -> str:
    if tech_score >= 80:
        return "STRONG_BUY_SIGNAL"
    if tech_score >= 65:
        return "BUY_SIGNAL"
    if tech_score >= 45:
        return "NEUTRAL"
    if tech_score >= 30:
        return "SELL_SIGNAL"
    return "STRONG_SELL_SIGNAL"
