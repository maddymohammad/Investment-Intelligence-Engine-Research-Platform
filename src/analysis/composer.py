"""
StockAnalyser: orchestrates all analysis modules into a single AnalysisResult per stock.

Consumed by the selection engine (Phase 2) and the AI deep-analyst (Phase 3).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd

from .fundamental import score_fundamentals
from .risk import score_risk
from .sector import (
    fetch_sector_performance,
    get_sector_relative_strength,
    sector_score_bonus,
)
from .technical import score_technicals
from .valuation import score_valuation

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    symbol: str
    run_date: date

    # Dimension scores (0-100)
    fundamental_score: float = 50.0
    technical_score: float = 50.0
    valuation_score: float = 50.0
    risk_score: float = 50.0
    sentiment_score: float = 50.0       # placeholder; filled by AI layer (Phase 3)

    # Composite (0-100); computed via compute_composite()
    composite_score: float = 0.0

    # Technical signals
    rsi: Optional[float] = None
    macd_signal: Optional[str] = None   # BULLISH | BEARISH
    technical_signals: dict = field(default_factory=dict)

    # Risk details
    beta: Optional[float] = None
    volatility_annual_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None

    # Valuation details
    valuation_details: dict = field(default_factory=dict)

    # Sector
    sector: Optional[str] = None
    sector_relative_strength: Optional[float] = None
    sector_bonus: float = 0.0

    # Current price (populated from price collector)
    current_price: Optional[float] = None

    def compute_composite(self) -> float:
        """
        Weighted composite of scored dimensions plus sector rotation bonus.
        Weights mirror config/constants.py SCORE_WEIGHTS; sentiment defaults
        to 50 (neutral) until the AI layer populates it in Phase 3.
        """
        from config.constants import SCORE_WEIGHTS

        base = (
            self.fundamental_score * SCORE_WEIGHTS["fundamental"] +
            self.technical_score  * SCORE_WEIGHTS["technical"] +
            self.sentiment_score  * SCORE_WEIGHTS["sentiment"] +
            self.risk_score       * SCORE_WEIGHTS["macro"]       # macro weight used for risk
        )
        self.composite_score = max(0.0, min(100.0, base + self.sector_bonus))
        return self.composite_score

    def to_db_dict(self) -> dict:
        """Serialize to the shape expected by AnalysisRepository.create()."""
        import json
        return {
            "run_date": self.run_date,
            "symbol": self.symbol,
            "fundamental_score": self.fundamental_score,
            "technical_score": self.technical_score,
            "valuation_score": self.valuation_score,
            "risk_score": self.risk_score,
            "sentiment_score": self.sentiment_score,
            "composite_score": self.composite_score,
            "raw_data": json.dumps({
                "technical_signals": self.technical_signals,
                "valuation_details": self.valuation_details,
                "beta": self.beta,
                "volatility_annual_pct": self.volatility_annual_pct,
                "max_drawdown_pct": self.max_drawdown_pct,
                "sector_relative_strength": self.sector_relative_strength,
            }),
        }


class StockAnalyser:
    """
    Analyse a stock (or batch) using the full scoring pipeline.

    Usage:
        analyser = StockAnalyser(price_collector, fundamental_collector)
        result = analyser.analyse("RELIANCE.NS")
    """

    def __init__(
        self,
        price_collector,
        fundamental_collector,
        nifty_df: Optional[pd.DataFrame] = None,
        sector_performance: Optional[dict] = None,
    ) -> None:
        self.prices = price_collector
        self.fundamentals = fundamental_collector
        self.nifty_df = nifty_df
        self.sector_performance: dict = sector_performance or {}

    @classmethod
    def build(
        cls,
        yahoo_provider=None,
        screener_provider=None,
        fetch_sector: bool = True,
    ) -> "StockAnalyser":
        """Factory: create a fully wired StockAnalyser with one call."""
        from src.data.collectors.fundamental import FundamentalCollector
        from src.data.collectors.price import PriceCollector
        from src.data.providers.yahoo import YahooProvider
        from config.constants import NIFTY50_INDEX

        yp = yahoo_provider or YahooProvider()
        pc = PriceCollector(provider=yp)
        fc = FundamentalCollector(yahoo=yp, screener=screener_provider, use_screener=screener_provider is not None)

        nifty_df = pc.collect(NIFTY50_INDEX, period="3mo")
        sector_perf = {}
        if fetch_sector and nifty_df is not None:
            sector_perf = fetch_sector_performance(yp, nifty_df, period="1mo")

        return cls(pc, fc, nifty_df=nifty_df, sector_performance=sector_perf)

    def analyse(
        self,
        symbol: str,
        run_date: Optional[date] = None,
        fund_data: Optional[dict] = None,
    ) -> AnalysisResult:
        from datetime import date as _date
        rd = run_date or _date.today()
        result = AnalysisResult(symbol=symbol, run_date=rd)

        # 1. Fundamentals (use pre-collected data if supplied to avoid double fetch)
        fund_data = fund_data or self.fundamentals.collect(symbol)
        result.fundamental_score = score_fundamentals(fund_data)
        result.sector = fund_data.get("sector")
        result.current_price = fund_data.get("current_price")

        # 2. Prices → Technical + Risk
        prices_df = self.prices.collect(symbol, period="1y")
        if prices_df is not None and not prices_df.empty:
            if result.current_price is None and not prices_df.empty:
                result.current_price = float(prices_df["Close"].iloc[-1])

            result.technical_score, tech_signals = score_technicals(prices_df)
            result.technical_signals = tech_signals
            result.rsi = tech_signals.get("rsi")
            result.macd_signal = tech_signals.get("macd")

            result.risk_score, risk_details = score_risk(prices_df, benchmark_df=self.nifty_df)
            result.beta = risk_details.get("beta")
            result.volatility_annual_pct = risk_details.get("volatility_annual_pct")
            result.max_drawdown_pct = risk_details.get("max_drawdown_pct")

        # 3. Valuation
        result.valuation_score, val_details = score_valuation(fund_data)
        result.valuation_details = val_details

        # 4. Sector rotation
        rs = get_sector_relative_strength(result.sector, self.sector_performance)
        result.sector_relative_strength = rs
        result.sector_bonus = sector_score_bonus(rs)

        # 5. Composite
        result.compute_composite()

        logger.debug(
            "%s → F:%.1f T:%.1f V:%.1f R:%.1f → composite:%.1f",
            symbol,
            result.fundamental_score,
            result.technical_score,
            result.valuation_score,
            result.risk_score,
            result.composite_score,
        )
        return result

    def analyse_bulk(
        self,
        symbols: list[str],
        run_date: Optional[date] = None,
    ) -> dict[str, AnalysisResult]:
        results: dict[str, AnalysisResult] = {}
        for sym in symbols:
            try:
                results[sym] = self.analyse(sym, run_date)
            except Exception as e:
                logger.error("Analysis failed for %s: %s", sym, e)
        return results
