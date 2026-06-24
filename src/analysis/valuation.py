"""
Valuation scoring: 0 (severely overvalued) → 100 (deeply undervalued).

Assesses whether the current price is justified by growth and peer comparison.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def score_valuation(
    data: dict,
    sector_avg_pe: Optional[float] = None,
) -> tuple[float, dict]:
    """
    Returns (score 0-100, details dict).

    sector_avg_pe is populated by sector.py; when absent, absolute PE thresholds
    tuned to Indian equity market norms are used.
    """
    scores: list[float] = []
    weights: list[float] = []
    details: dict = {}

    pe = data.get("pe_ratio")
    peg = data.get("peg_ratio")
    pb = data.get("price_to_book")

    # ── 1. PEG ratio: growth-adjusted PE ─────────────────────────
    if peg is not None and 0 < peg < 50:
        details["peg"] = round(peg, 2)
        s = (
            100 if peg < 0.5 else
            90  if peg < 0.75 else
            75  if peg < 1.0 else
            55  if peg < 1.5 else
            35  if peg < 2.0 else
            15
        )
        scores.append(s); weights.append(0.40)

    # ── 2. P/E ratio ─────────────────────────────────────────────
    if pe is not None and pe > 0:
        if sector_avg_pe and sector_avg_pe > 0:
            discount_pct = (sector_avg_pe - pe) / sector_avg_pe * 100
            details["pe_vs_sector_pct"] = round(discount_pct, 1)
            s = (
                100 if discount_pct > 30 else
                85  if discount_pct > 15 else
                70  if discount_pct > 0  else
                55  if discount_pct > -15 else
                35  if discount_pct > -30 else
                10
            )
        else:
            details["pe_absolute"] = round(pe, 1)
            # Indian market context: Nifty 50 historically 18-25x
            s = (
                80  if pe < 10 else    # very cheap (may be value trap)
                100 if pe < 20 else    # fair value
                80  if pe < 30 else
                55  if pe < 40 else
                25  if pe < 60 else
                10
            )
        scores.append(s); weights.append(0.40)

    # ── 3. Price / Book ───────────────────────────────────────────
    if pb is not None and pb > 0:
        details["price_to_book"] = round(pb, 2)
        s = (
            100 if pb < 1.0 else   # trading below book
            85  if pb < 2.0 else
            65  if pb < 3.0 else
            45  if pb < 5.0 else
            25  if pb < 8.0 else
            10
        )
        scores.append(s); weights.append(0.20)

    if not scores:
        return 50.0, details

    total_w = sum(weights)
    return _clamp(sum(s * w for s, w in zip(scores, weights)) / total_w), details
