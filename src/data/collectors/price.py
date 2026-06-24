from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from src.data.providers.yahoo import YahooProvider

logger = logging.getLogger(__name__)


class PriceCollector:
    """Collects OHLCV price data for one or many symbols."""

    def __init__(self, provider: Optional[YahooProvider] = None) -> None:
        self.provider = provider or YahooProvider()

    def collect(self, symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
        """Return daily OHLCV DataFrame for a single symbol."""
        df = self.provider.get_prices(symbol, period=period)
        if df is None or df.empty:
            logger.warning("No price data returned for %s", symbol)
            return None
        return df

    def collect_bulk(
        self, symbols: list[str], period: str = "1y"
    ) -> dict[str, pd.DataFrame]:
        """Return {symbol: DataFrame} for multiple symbols in one download."""
        if not symbols:
            return {}
        result = self.provider.get_prices_bulk(symbols, period=period)
        missing = [s for s in symbols if s not in result]
        if missing:
            logger.info("No price data for %d symbols: %s", len(missing), missing[:5])
        return result

    def get_latest_close(self, symbol: str) -> Optional[float]:
        """Return the most recent closing price for a symbol."""
        df = self.collect(symbol, period="5d")
        if df is None or df.empty:
            return None
        return float(df["Close"].iloc[-1])

    def collect_index(self, ticker: str) -> Optional[float]:
        """Return latest close for a market index (e.g. '^NSEI')."""
        return self.provider.get_index_close(ticker)
