"""
Technical indicator scoring: 0 (very bearish) → 100 (very bullish).

Indicators computed: RSI, MACD, SMA crossover, volume trend, ADX.
Requires a pandas DataFrame with at minimum a 'Close' column (OHLCV preferred).
Uses the `ta` library (pure Python, no C dependencies).
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def score_technicals(df: Optional[pd.DataFrame]) -> tuple[float, dict]:
    """
    Returns (score 0-100, signals dict).
    Falls back to neutral (50, {}) when data is absent or too short.
    """
    if df is None or len(df) < 20:
        return 50.0, {}

    try:
        import ta
    except ImportError:
        logger.warning("ta library not installed; technical scoring skipped")
        return 50.0, {}

    close = df["Close"].dropna()
    signals: dict = {}
    scores: list[float] = []
    weights: list[float] = []

    # ── 1. RSI (14-day) ──────────────────────────────────────────
    if len(close) >= 15:
        rsi_series = ta.momentum.RSIIndicator(close=close, window=14).rsi().dropna()
        if not rsi_series.empty:
            rsi = float(rsi_series.iloc[-1])
            signals["rsi"] = round(rsi, 1)
            s = (
                100 if rsi < 30 else   # oversold
                85  if rsi < 40 else
                65  if rsi < 60 else   # neutral
                40  if rsi < 70 else
                15                      # overbought
            )
            scores.append(s); weights.append(0.25)

    # ── 2. MACD ───────────────────────────────────────────────────
    if len(close) >= 35:
        macd_ind = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
        macd_line = macd_ind.macd().dropna()
        macd_signal = macd_ind.macd_signal().dropna()
        macd_hist = macd_ind.macd_diff().dropna()
        if not macd_line.empty and not macd_signal.empty:
            m = float(macd_line.iloc[-1])
            sig = float(macd_signal.iloc[-1])
            hist = float(macd_hist.iloc[-1]) if not macd_hist.empty else 0.0
            signals["macd"] = "BULLISH" if m > sig else "BEARISH"
            signals["macd_histogram"] = round(hist, 4)
            s = (
                90 if m > sig and m > 0 else    # MACD above signal AND positive
                70 if m > sig else               # MACD above signal, still negative
                35 if m <= sig and m > 0 else   # MACD below signal, but positive
                15                               # bearish
            )
            scores.append(s); weights.append(0.25)

    # ── 3. Moving average position (50-day / 200-day) ────────────
    if len(close) >= 50:
        sma50 = ta.trend.SMAIndicator(close=close, window=50).sma_indicator().dropna()
        price = float(close.iloc[-1])
        if not sma50.empty:
            s50 = float(sma50.iloc[-1])
            if len(close) >= 200:
                sma200 = ta.trend.SMAIndicator(close=close, window=200).sma_indicator().dropna()
                if not sma200.empty:
                    s200 = float(sma200.iloc[-1])
                    signals["ma_position"] = (
                        "ABOVE_BOTH" if price > s50 > s200 else
                        "BETWEEN"    if price > s200 else
                        "BELOW_BOTH"
                    )
                    s = (
                        100 if price > s50 > s200 else   # golden zone
                        65  if price > s50 or price > s200 else
                        15  if price < s50 < s200 else   # death zone
                        40
                    )
                else:
                    s = 75 if price > s50 else 30
                    signals["ma_position"] = "ABOVE_SMA50" if price > s50 else "BELOW_SMA50"
            else:
                s = 75 if price > s50 else 30
                signals["ma_position"] = "ABOVE_SMA50" if price > s50 else "BELOW_SMA50"
            scores.append(s); weights.append(0.25)

    # ── 4. Volume trend ───────────────────────────────────────────
    if "Volume" in df.columns and len(df) >= 20:
        vol = df["Volume"].dropna()
        price_ret_5d = close.pct_change().dropna().iloc[-5:].mean() if len(close) >= 5 else 0.0
        recent_vol = float(vol.iloc[-5:].mean()) if len(vol) >= 5 else float(vol.mean())
        avg_vol_20d = float(vol.iloc[-20:].mean())
        ratio = recent_vol / avg_vol_20d if avg_vol_20d > 0 else 1.0
        signals["volume_ratio_5d_vs_20d"] = round(ratio, 2)
        s = (
            90 if ratio > 1.2 and price_ret_5d > 0 else   # volume confirms up move
            25 if ratio > 1.2 and price_ret_5d <= 0 else  # volume confirms down move
            65 if ratio >= 0.8 else                         # normal volume
            50                                              # low volume / weak signal
        )
        scores.append(s); weights.append(0.15)

    # ── 5. Trend strength (ADX) ───────────────────────────────────
    if all(c in df.columns for c in ("High", "Low", "Close")) and len(df) >= 28:
        adx_series = ta.trend.ADXIndicator(
            high=df["High"].dropna(),
            low=df["Low"].dropna(),
            close=close,
            window=14,
        ).adx().dropna()
        if not adx_series.empty:
            adx = float(adx_series.iloc[-1])
            signals["adx"] = round(adx, 1)
            # ADX measures trend strength, not direction; combine with MA position
            ma_pos = signals.get("ma_position", "")
            uptrend = "ABOVE" in ma_pos
            s = (
                90 if adx > 25 and uptrend else
                25 if adx > 25 and not uptrend else
                65 if adx > 20 else
                50  # range-bound / no trend
            )
            scores.append(s); weights.append(0.10)

    if not scores:
        return 50.0, signals

    total_w = sum(weights)
    score = sum(s * w for s, w in zip(scores, weights)) / total_w
    return _clamp(score), signals
