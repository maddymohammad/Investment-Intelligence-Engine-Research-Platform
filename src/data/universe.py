from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from config.constants import (
    NIFTY50_SYMBOLS,
    NSE_NIFTY500_CSV_URL,
    NSE_NIFTY50_CSV_URL,
    SYMBOL_TO_SECTOR,
)
from config.settings import get_settings

logger = logging.getLogger(__name__)

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://niftyindices.com/",
}


class UniverseManager:
    """Builds and categorises the tradeable stock universe."""

    def __init__(self, yahoo_provider) -> None:
        self.yahoo = yahoo_provider
        self._settings = get_settings()

    def categorise_by_market_cap(self, market_cap_cr: Optional[float]) -> str:
        if market_cap_cr is None:
            return "MID"
        if market_cap_cr < self._settings.small_cap_max_market_cap_cr:
            return "SMALL"
        if market_cap_cr >= self._settings.large_cap_min_market_cap_cr:
            return "LARGE"
        return "MID"

    def fetch_universe(self) -> list[dict]:
        """
        Returns a list of {symbol, name, exchange} dicts for the full universe.
        Tries NIFTY 500 CSV from NSE India first; falls back to hardcoded NIFTY 50.
        """
        for url in [NSE_NIFTY500_CSV_URL, NSE_NIFTY50_CSV_URL]:
            stocks = self._try_fetch_nse_csv(url)
            if stocks:
                logger.info("Fetched %d stocks from NSE CSV: %s", len(stocks), url)
                return stocks

        logger.warning("NSE CSV unavailable — using hardcoded NIFTY 50 fallback")
        return self._nifty50_fallback()

    def _try_fetch_nse_csv(self, url: str) -> list[dict]:
        try:
            resp = requests.get(url, headers=_NSE_HEADERS, timeout=20)
            resp.raise_for_status()
            lines = resp.text.strip().splitlines()
            stocks = []
            for line in lines[1:]:  # skip header
                parts = [p.strip().strip('"') for p in line.split(",")]
                if len(parts) >= 3 and parts[2]:
                    stocks.append(
                        {
                            "name": parts[0],
                            "symbol": parts[2] + ".NS",
                            "exchange": "NSE",
                        }
                    )
            return stocks
        except Exception as e:
            logger.debug("NSE CSV fetch failed (%s): %s", url, e)
            return []

    def _nifty50_fallback(self) -> list[dict]:
        return [
            {"symbol": s, "exchange": "NSE", "name": s.replace(".NS", "")}
            for s in NIFTY50_SYMBOLS
        ]

    def enrich(self, stock: dict, delay: float = 0.5) -> dict:
        """
        Add market cap, sector, industry, and cap_category to a stock dict
        by calling Yahoo Finance. Sleeps `delay` seconds to avoid rate-limits.
        """
        info = self.yahoo.get_info(stock["symbol"])
        time.sleep(delay)

        mc_cr = self.yahoo.get_market_cap_cr(info)
        sector = (
            info.get("sector")
            or SYMBOL_TO_SECTOR.get(stock["symbol"])
        )

        return {
            **stock,
            "name": info.get("longName") or info.get("shortName") or stock.get("name", ""),
            "sector": sector,
            "industry": info.get("industry"),
            "market_cap_cr": mc_cr,
            "cap_category": self.categorise_by_market_cap(mc_cr),
            "is_active": True,
        }
