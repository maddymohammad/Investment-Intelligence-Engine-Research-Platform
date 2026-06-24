from __future__ import annotations

import logging
from typing import Optional

from src.data.providers.yahoo import YahooProvider
from src.data.providers.screener_in import ScreenerInProvider

logger = logging.getLogger(__name__)


class FundamentalCollector:
    """
    Combines data from Yahoo Finance (primary) and Screener.in (supplement).
    Yahoo provides most metrics; Screener provides ROCE and verified D/E.
    """

    def __init__(
        self,
        yahoo: Optional[YahooProvider] = None,
        screener: Optional[ScreenerInProvider] = None,
        use_screener: bool = True,
    ) -> None:
        self.yahoo = yahoo or YahooProvider()
        self.screener = screener or ScreenerInProvider() if use_screener else None

    def collect(self, symbol: str) -> dict:
        """
        Return a merged fundamental dict for `symbol`.
        Keys: all fields from YahooProvider.extract_fundamentals() plus
              roce, revenue_growth_10yr, revenue_growth_5yr, profit_growth_10yr
              (from Screener.in when available).
        """
        data = self.yahoo.extract_fundamentals(symbol)

        if self.screener:
            try:
                sc_data = self.screener.get_fundamentals(symbol)
                # Screener.in ROCE and growth rates override yfinance where present
                for key in ("roce", "revenue_growth_10yr", "revenue_growth_5yr", "profit_growth_10yr"):
                    if sc_data.get(key) is not None:
                        data[key] = sc_data[key]
                # Use Screener D/E if yfinance returned None
                if data.get("debt_to_equity") is None and sc_data.get("debt_to_equity") is not None:
                    data["debt_to_equity"] = sc_data["debt_to_equity"]
                # Use Screener market cap in Crore if more accurate
                if sc_data.get("market_cap_cr") is not None:
                    data["market_cap_cr_screener"] = sc_data["market_cap_cr"]
            except Exception as e:
                logger.warning("Screener.in supplement failed for %s: %s", symbol, e)

        return data

    def collect_bulk(self, symbols: list[str]) -> dict[str, dict]:
        """Return {symbol: fundamentals_dict} for a list of symbols."""
        result = {}
        for sym in symbols:
            try:
                result[sym] = self.collect(sym)
            except Exception as e:
                logger.error("Fundamental collection failed for %s: %s", sym, e)
                result[sym] = {"symbol": sym}
        return result
