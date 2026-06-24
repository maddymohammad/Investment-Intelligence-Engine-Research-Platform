from __future__ import annotations

import logging
import time
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# 1 Crore INR = 10,000,000 INR
_CR = 10_000_000


class YahooProvider:
    """Wrapper around yfinance for NSE/BSE price and info data."""

    def __init__(self, request_delay: float = 0.4) -> None:
        self.delay = request_delay

    # ─── Single-ticker price ──────────────────────────────────────

    def get_prices(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> Optional[pd.DataFrame]:
        try:
            df = yf.Ticker(symbol).history(
                period=period, interval=interval, auto_adjust=True
            )
            time.sleep(self.delay)
            return df if not df.empty else None
        except Exception as e:
            logger.warning("Price fetch failed for %s: %s", symbol, e)
            return None

    # ─── Bulk price download ──────────────────────────────────────

    def get_prices_bulk(
        self,
        symbols: list[str],
        period: str = "1y",
        interval: str = "1d",
    ) -> dict[str, pd.DataFrame]:
        if not symbols:
            return {}
        try:
            raw = yf.download(
                tickers=" ".join(symbols),
                period=period,
                interval=interval,
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
            result: dict[str, pd.DataFrame] = {}
            if len(symbols) == 1:
                if not raw.empty:
                    result[symbols[0]] = raw
            else:
                for sym in symbols:
                    try:
                        df = raw[sym].dropna(how="all")
                        if not df.empty:
                            result[sym] = df
                    except KeyError:
                        pass
            return result
        except Exception as e:
            logger.error("Bulk price download failed: %s", e)
            return {}

    # ─── Ticker info (fundamentals) ───────────────────────────────

    def get_info(self, symbol: str) -> dict:
        try:
            info = yf.Ticker(symbol).info
            time.sleep(self.delay)
            return info or {}
        except Exception as e:
            logger.warning("Info fetch failed for %s: %s", symbol, e)
            return {}

    # ─── Derived helpers ──────────────────────────────────────────

    def get_market_cap_cr(self, info: dict) -> Optional[float]:
        """Return market cap in Crore INR from yfinance info dict."""
        mc = info.get("marketCap")
        return round(mc / _CR, 2) if mc else None

    def extract_fundamentals(self, symbol: str) -> dict:
        """
        Pull a flat dict of fundamental metrics from yfinance .info.
        All values are raw floats; None if unavailable.
        """
        info = self.get_info(symbol)
        mc_cr = self.get_market_cap_cr(info)

        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName", ""),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "exchange": info.get("exchange", "NSE"),
            "market_cap_cr": mc_cr,
            # Valuation
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            # Quality
            "roe": info.get("returnOnEquity"),          # decimal, e.g. 0.18
            "roa": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            # Growth
            "revenue_growth": info.get("revenueGrowth"),   # YoY decimal
            "earnings_growth": info.get("earningsGrowth"),
            # Profitability
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "gross_margin": info.get("grossMargins"),
            # Cash flow
            "free_cashflow": info.get("freeCashflow"),
            "operating_cashflow": info.get("operatingCashflow"),
            # Per share
            "eps_ttm": info.get("trailingEps"),
            "book_value": info.get("bookValue"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            # Dividend
            "dividend_yield": info.get("dividendYield"),
            # Beta
            "beta": info.get("beta"),
        }

    def get_index_close(self, ticker: str) -> Optional[float]:
        """Return latest closing price for an index (e.g. '^NSEI')."""
        try:
            hist = yf.Ticker(ticker).history(period="2d", auto_adjust=True)
            if hist.empty:
                return None
            return float(hist["Close"].iloc[-1])
        except Exception as e:
            logger.warning("Index fetch failed for %s: %s", ticker, e)
            return None
