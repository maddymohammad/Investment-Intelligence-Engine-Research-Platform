from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MacroCollector:
    """
    Collects macro-economic indicators from FRED (global) and
    Google News RSS (India market news / sentiment headlines).
    """

    def __init__(self, fred_api_key: Optional[str] = None) -> None:
        self.fred_api_key = fred_api_key
        self._fred = None

    def _get_fred(self):
        if self._fred is None:
            if not self.fred_api_key:
                return None
            try:
                from fredapi import Fred
                self._fred = Fred(api_key=self.fred_api_key)
            except ImportError:
                logger.warning("fredapi not installed; macro FRED data skipped")
        return self._fred

    def collect(self) -> dict:
        data: dict = {}

        fred = self._get_fred()
        if fred:
            data.update(self._fetch_fred(fred))

        data["india_market_headlines"] = self._fetch_india_news()
        return data

    def _fetch_fred(self, fred) -> dict:
        """Fetch key US/global macro series from FRED."""
        series_map = {
            "fed_funds_rate": "FEDFUNDS",
            "wti_crude_usd": "DCOILWTICO",
        }
        result: dict = {}
        for key, series_id in series_map.items():
            try:
                s = fred.get_series(series_id).dropna()
                result[key] = float(s.iloc[-1])
            except Exception as e:
                logger.debug("FRED series %s failed: %s", series_id, e)

        # YoY CPI separately (needs pct_change)
        try:
            cpi = fred.get_series("CPIAUCSL").dropna()
            result["us_cpi_yoy_pct"] = float(cpi.pct_change(12).dropna().iloc[-1] * 100)
        except Exception as e:
            logger.debug("US CPI fetch failed: %s", e)

        return result

    def _fetch_india_news(self) -> list[str]:
        """Return up to 10 recent India market news headlines via Google News RSS."""
        try:
            import feedparser
            url = (
                "https://news.google.com/rss/search"
                "?q=indian+stock+market+NSE+BSE&hl=en-IN&gl=IN&ceid=IN:en"
            )
            feed = feedparser.parse(url)
            return [entry.title for entry in feed.entries[:10]]
        except Exception as e:
            logger.warning("News RSS fetch failed: %s", e)
            return []
