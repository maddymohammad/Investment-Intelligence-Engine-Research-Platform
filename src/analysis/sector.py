"""
Sector rotation analysis for Indian equity markets.

Computes relative strength of NSE sector indices vs NIFTY 50.
Results inform stock selection — stocks in leading sectors get a
mild composite score boost applied by the ranker.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# NSE sector index tickers on Yahoo Finance
SECTOR_TICKERS: dict[str, str] = {
    "Information Technology": "^CNXIT",
    "Financials": "^NSEBANK",
    "Pharma": "^CNXPHARMA",
    "Consumer Staples": "^CNXFMCG",
    "Auto": "^CNXAUTO",
    "Metal": "^CNXMETAL",
    "Realty": "^CNXREALTY",
    "Energy": "^CNXENERGY",
    "Infra": "^CNXINFRA",
    "PSE": "^CNXPSE",
}

# Sector aliases — yfinance sector strings → SECTOR_TICKERS keys
SECTOR_ALIAS: dict[str, str] = {
    "Technology": "Information Technology",
    "Financial Services": "Financials",
    "Basic Materials": "Metal",
    "Healthcare": "Pharma",
    "Consumer Defensive": "Consumer Staples",
    "Consumer Cyclical": "Auto",
    "Industrials": "Infra",
    "Utilities": "Energy",
    "Real Estate": "Realty",
    "Communication Services": "Information Technology",
}


def fetch_sector_performance(
    yahoo_provider,
    nifty_df: Optional[pd.DataFrame],
    period: str = "1mo",
) -> dict[str, dict]:
    """
    Returns {sector_name: {return_pct, relative_strength, momentum_label}}.
    relative_strength > 0 means the sector beat NIFTY 50 over the period.
    """
    if nifty_df is None or nifty_df.empty:
        logger.warning("No NIFTY 50 data; sector relative strength skipped")
        return {}

    nifty_close = nifty_df["Close"].dropna()
    if len(nifty_close) < 2:
        return {}

    nifty_return = float(
        (nifty_close.iloc[-1] / nifty_close.iloc[0] - 1) * 100
    )

    performance: dict[str, dict] = {}

    for sector_name, ticker in SECTOR_TICKERS.items():
        df = yahoo_provider.get_prices(ticker, period=period)
        if df is None or df.empty:
            logger.debug("No data for sector index %s (%s)", sector_name, ticker)
            continue

        sec_close = df["Close"].dropna()
        if len(sec_close) < 2:
            continue

        sector_return = float((sec_close.iloc[-1] / sec_close.iloc[0] - 1) * 100)
        rs = sector_return - nifty_return

        performance[sector_name] = {
            "return_pct": round(sector_return, 2),
            "relative_strength": round(rs, 2),
            "momentum_label": (
                "STRONG_OUTPERFORM" if rs > 3 else
                "OUTPERFORM"        if rs > 0 else
                "UNDERPERFORM"      if rs > -3 else
                "STRONG_UNDERPERFORM"
            ),
        }

    return performance


def get_sector_relative_strength(
    sector: Optional[str],
    sector_performance: dict[str, dict],
) -> Optional[float]:
    """
    Return relative_strength (%) for a stock's sector.
    Returns None when the sector is not tracked or data is unavailable.
    """
    if not sector or not sector_performance:
        return None

    # Try exact match first
    if sector in sector_performance:
        return sector_performance[sector]["relative_strength"]

    # Try alias resolution
    canonical = SECTOR_ALIAS.get(sector)
    if canonical and canonical in sector_performance:
        return sector_performance[canonical]["relative_strength"]

    # Partial string match as last resort
    sector_lower = sector.lower()
    for name, perf in sector_performance.items():
        if name.lower() in sector_lower or sector_lower in name.lower():
            return perf["relative_strength"]

    return None


def sector_score_bonus(relative_strength: Optional[float]) -> float:
    """
    Return a small additive bonus (0–8 points) for stocks in leading sectors.
    Applied by the ranker on top of the composite score.
    """
    if relative_strength is None:
        return 0.0
    if relative_strength > 5:
        return 8.0
    if relative_strength > 3:
        return 5.0
    if relative_strength > 0:
        return 2.0
    if relative_strength < -5:
        return -5.0
    if relative_strength < -2:
        return -2.0
    return 0.0
