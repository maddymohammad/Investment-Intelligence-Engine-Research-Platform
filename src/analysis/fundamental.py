"""
Fundamental quality scoring: 0 (poor) → 100 (excellent).

Each metric is scored independently on a 0-100 scale then combined with
weights that reflect its predictive importance for Indian equity returns.
Missing metrics reduce the effective weight pool — the score always stays
on a 0-100 scale regardless of data completeness.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _weighted_average(scores: list[float], weights: list[float]) -> float:
    total_w = sum(weights)
    if total_w == 0:
        return 50.0
    return _clamp(sum(s * w for s, w in zip(scores, weights)) / total_w)


def score_fundamentals(data: dict) -> float:
    """
    Score fundamental quality.  Accepts the dict returned by
    FundamentalCollector.collect() or YahooProvider.extract_fundamentals().
    """
    scores: list[float] = []
    weights: list[float] = []

    # ── ROE: Return on Equity ─────────────────────────────────────
    roe = data.get("roe")
    if roe is not None:
        r = roe * 100  # yfinance returns decimal
        s = (
            100 if r >= 25 else
            85  if r >= 20 else
            70  if r >= 15 else
            50  if r >= 10 else
            30  if r >= 5  else
            10  if r >= 0  else
            0
        )
        scores.append(s); weights.append(0.20)

    # ── ROCE: Return on Capital Employed ──────────────────────────
    roce = data.get("roce")
    if roce is not None:
        r = roce if roce > 1.5 else roce * 100  # screener.in returns %; yfinance decimal
        s = (
            100 if r >= 25 else
            80  if r >= 18 else
            60  if r >= 12 else
            40  if r >= 8  else
            15
        )
        scores.append(s); weights.append(0.15)

    # ── Debt / Equity ─────────────────────────────────────────────
    de = data.get("debt_to_equity")
    if de is not None:
        s = (
            100 if de <= 0.1 else
            90  if de <= 0.3 else
            80  if de <= 0.5 else
            60  if de <= 1.0 else
            35  if de <= 2.0 else
            15  if de <= 3.0 else
            0
        )
        scores.append(s); weights.append(0.15)

    # ── Revenue Growth (YoY, decimal) ────────────────────────────
    rg = data.get("revenue_growth")
    if rg is not None:
        r = rg * 100
        s = (
            100 if r >= 25 else
            80  if r >= 15 else
            65  if r >= 10 else
            50  if r >= 5  else
            25  if r >= 0  else
            5
        )
        scores.append(s); weights.append(0.15)

    # ── Net Profit Margin (decimal) ───────────────────────────────
    pm = data.get("profit_margin")
    if pm is not None:
        r = pm * 100
        s = (
            100 if r >= 25 else
            80  if r >= 15 else
            65  if r >= 10 else
            50  if r >= 5  else
            20  if r >= 0  else
            0
        )
        scores.append(s); weights.append(0.15)

    # ── EPS Growth (YoY, decimal) ─────────────────────────────────
    eg = data.get("earnings_growth")
    if eg is not None:
        r = eg * 100
        s = (
            100 if r >= 30 else
            80  if r >= 20 else
            60  if r >= 10 else
            35  if r >= 0  else
            5
        )
        scores.append(s); weights.append(0.10)

    # ── P/E Ratio ─────────────────────────────────────────────────
    pe = data.get("pe_ratio")
    if pe is not None and pe > 0:
        s = (
            75  if pe <= 10 else   # possibly cheap, or value trap
            100 if pe <= 20 else   # sweet spot for Indian markets
            80  if pe <= 30 else
            55  if pe <= 40 else
            30  if pe <= 60 else
            10
        )
        scores.append(s); weights.append(0.10)

    # ── Operating Margin ─────────────────────────────────────────
    om = data.get("operating_margin")
    if om is not None:
        r = om * 100
        s = (
            100 if r >= 30 else
            80  if r >= 20 else
            60  if r >= 12 else
            40  if r >= 5  else
            15  if r >= 0  else
            0
        )
        scores.append(s); weights.append(0.10)

    if not scores:
        logger.debug("No fundamental data for scoring; returning neutral 50")
        return 50.0

    return _weighted_average(scores, weights)
