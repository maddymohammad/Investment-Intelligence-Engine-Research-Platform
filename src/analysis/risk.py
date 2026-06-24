"""
Risk scoring: 0 (extreme risk) → 100 (very low risk).

Lower risk score does not automatically exclude a stock — it informs the
confidence calculation and is presented in the report's risk section.
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def score_risk(
    df: Optional[pd.DataFrame],
    benchmark_df: Optional[pd.DataFrame] = None,
) -> tuple[float, dict]:
    """
    Returns (score 0-100, details dict).
    benchmark_df should be a NIFTY 50 price DataFrame with a 'Close' column.
    """
    if df is None or len(df) < 30:
        return 50.0, {}

    close = df["Close"].dropna()
    returns = close.pct_change().dropna()

    details: dict = {}
    scores: list[float] = []
    weights: list[float] = []

    # ── 1. Annualised volatility ──────────────────────────────────
    vol_annual = float(returns.std() * np.sqrt(252) * 100)
    details["volatility_annual_pct"] = round(vol_annual, 1)
    s = (
        100 if vol_annual < 15 else
        80  if vol_annual < 25 else
        60  if vol_annual < 35 else
        40  if vol_annual < 45 else
        20  if vol_annual < 60 else
        5
    )
    scores.append(s); weights.append(0.35)

    # ── 2. Maximum drawdown ───────────────────────────────────────
    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    max_dd = float(abs(drawdown.min()) * 100)
    details["max_drawdown_pct"] = round(max_dd, 1)
    s = (
        100 if max_dd < 10 else
        80  if max_dd < 20 else
        60  if max_dd < 30 else
        35  if max_dd < 40 else
        15  if max_dd < 60 else
        5
    )
    scores.append(s); weights.append(0.35)

    # ── 3. Beta vs benchmark ──────────────────────────────────────
    if benchmark_df is not None and len(benchmark_df) >= 30:
        bench_close = benchmark_df["Close"].dropna()
        bench_ret = bench_close.pct_change().dropna()
        aligned = pd.concat([returns, bench_ret], axis=1, join="inner").dropna()
        if len(aligned) >= 20:
            cov = float(aligned.iloc[:, 0].cov(aligned.iloc[:, 1]))
            var = float(aligned.iloc[:, 1].var())
            beta = cov / var if var > 0 else 1.0
            details["beta"] = round(beta, 2)
            s = (
                100 if beta < 0.5 else
                85  if beta < 0.8 else
                75  if beta < 1.0 else
                60  if beta < 1.2 else
                40  if beta < 1.5 else
                20
            )
            scores.append(s); weights.append(0.30)

    if not scores:
        return 50.0, details

    total_w = sum(weights)
    score = sum(s * w for s, w in zip(scores, weights)) / total_w
    return _clamp(score), details
