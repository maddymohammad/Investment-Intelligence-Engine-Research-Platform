from __future__ import annotations

import logging
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.screener.in/company/{symbol}/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.screener.in/",
}


def _clean_number(text: str) -> Optional[float]:
    """Strip currency symbols, commas, % signs; return float or None."""
    cleaned = re.sub(r"[₹,\s%Cr.]", "", text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return None


class ScreenerInProvider:
    """
    Scrapes key ratios from Screener.in for Indian stocks.
    Primary value over yfinance: ROCE, accurate D/E, Indian-specific data.
    Rate-limited to 1 request/sec to avoid bans.
    """

    def __init__(self, request_delay: float = 1.2) -> None:
        self.delay = request_delay
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    def _nse_to_screener_symbol(self, symbol: str) -> str:
        """Convert 'RELIANCE.NS' → 'RELIANCE'."""
        return symbol.split(".")[0]

    def get_fundamentals(self, symbol: str) -> dict:
        """
        Return a dict of fundamental metrics scraped from Screener.in.
        Returns an empty dict on any failure; callers should treat None == missing.
        """
        sc_sym = self._nse_to_screener_symbol(symbol)
        url = _BASE_URL.format(symbol=sc_sym)
        time.sleep(self.delay)

        try:
            resp = self._session.get(url, timeout=15)
        except requests.RequestException as e:
            logger.warning("Screener.in request failed for %s: %s", symbol, e)
            return {}

        if resp.status_code == 404:
            logger.info("Screener.in: symbol not found %s", symbol)
            return {}
        if resp.status_code != 200:
            logger.warning("Screener.in HTTP %s for %s", resp.status_code, symbol)
            return {}

        soup = BeautifulSoup(resp.text, "lxml")
        data: dict = {"symbol": symbol}

        # ─── Top ratios section ───────────────────────────────────
        ratios_section = soup.find("ul", id="top-ratios") or soup.find(
            "section", id="top-ratios"
        )
        if ratios_section:
            for li in ratios_section.find_all("li"):
                name_el = li.find("span", class_="name")
                value_el = li.find("span", class_="value") or li.find(
                    "span", class_="nowrap value"
                )
                if not name_el or not value_el:
                    continue
                name = name_el.get_text(strip=True).lower()
                raw = value_el.get_text(strip=True)
                val = _clean_number(raw)

                if "market cap" in name:
                    data["market_cap_cr"] = val
                elif "stock p/e" in name or "pe" == name:
                    data["pe_ratio"] = val
                elif "roce" in name:
                    data["roce"] = val
                elif "roe" in name:
                    data["roe"] = val
                elif "book value" in name:
                    data["book_value"] = val
                elif "dividend yield" in name:
                    data["dividend_yield"] = val
                elif "face value" in name:
                    data["face_value"] = val
                elif "current price" in name:
                    data["current_price"] = val

        # ─── Debt/Equity from balance sheet table ─────────────────
        data["debt_to_equity"] = self._scrape_debt_to_equity(soup)

        # ─── 10-year profit growth ────────────────────────────────
        data.update(self._scrape_growth_rates(soup))

        return data

    def _scrape_debt_to_equity(self, soup: BeautifulSoup) -> Optional[float]:
        """Find D/E ratio in the balance sheet or ratios table."""
        for table in soup.find_all("table", class_="data-table"):
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if not cells:
                    continue
                label = cells[0].get_text(strip=True).lower()
                if "borrowings" in label or "debt/equity" in label:
                    # Take the most recent column (last non-empty cell)
                    for cell in reversed(cells[1:]):
                        val = _clean_number(cell.get_text(strip=True))
                        if val is not None:
                            return val
        return None

    def _scrape_growth_rates(self, soup: BeautifulSoup) -> dict:
        """Extract 10-year compounded growth rates from the ratios section."""
        result: dict = {}
        compounded_section = soup.find("section", id="compounded-growth-rates")
        if not compounded_section:
            return result

        for li in compounded_section.find_all("li"):
            spans = li.find_all("span")
            if len(spans) < 2:
                continue
            label = spans[0].get_text(strip=True).lower()
            value = _clean_number(spans[-1].get_text(strip=True))
            if "sales growth" in label or "revenue growth" in label:
                if "10 year" in label or "10yr" in label:
                    result["revenue_growth_10yr"] = value
                elif "5 year" in label or "5yr" in label:
                    result["revenue_growth_5yr"] = value
            elif "profit growth" in label:
                if "10 year" in label or "10yr" in label:
                    result["profit_growth_10yr"] = value
        return result
