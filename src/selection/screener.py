"""
Minimum quality filter: removes stocks with fundamental red flags
before ranking. This is a hard gate — it is intentionally conservative
because we never force recommendations.
"""
from __future__ import annotations

import logging
from typing import Optional

from config.settings import Settings, get_settings

logger = logging.getLogger(__name__)


class StockScreener:

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._s = settings or get_settings()

    def passes(self, fund_data: dict, cap_category: str) -> tuple[bool, str]:
        """
        Returns (passes: bool, rejection_reason: str).
        rejection_reason is empty when the stock passes.
        """
        symbol = fund_data.get("symbol", "?")

        # ── Must have a tradeable price ───────────────────────────
        price = fund_data.get("current_price")
        if not price or price <= 0:
            return False, f"{symbol}: no valid current price"

        # ── Loss-making companies excluded from Small Cap ─────────
        # Large caps are given more latitude (restructuring, investment phase)
        pm = fund_data.get("profit_margin")
        if pm is not None and pm < 0 and cap_category == "SMALL":
            return False, f"{symbol}: loss-making (profit margin {pm*100:.1f}%) — excluded from small cap"

        # ── Excessive debt ────────────────────────────────────────
        de = fund_data.get("debt_to_equity")
        if de is not None and de > 5.0:
            return False, f"{symbol}: D/E ratio {de:.1f} exceeds safety threshold of 5.0"

        # ── Unjustified extreme valuation ─────────────────────────
        pe = fund_data.get("pe_ratio")
        eg = fund_data.get("earnings_growth")
        if pe is not None and pe > 100:
            growth = (eg or 0) * 100
            if growth < 30:
                return False, (
                    f"{symbol}: P/E {pe:.0f}x without sufficient growth "
                    f"({growth:.0f}% EPS growth)"
                )

        # ── Negative revenue growth for small caps ────────────────
        rg = fund_data.get("revenue_growth")
        if rg is not None and rg < -0.10 and cap_category == "SMALL":
            return False, f"{symbol}: revenue shrinking {rg*100:.1f}% YoY — too risky for small cap"

        return True, ""

    def filter_by_cap(
        self,
        fundamentals: dict[str, dict],
        cap_category: str,
    ) -> list[str]:
        """
        Return symbols that (a) match cap_category and (b) pass minimum quality.
        """
        passed: list[str] = []
        for symbol, data in fundamentals.items():
            if data.get("cap_category") != cap_category:
                continue
            ok, reason = self.passes(data, cap_category)
            if ok:
                passed.append(symbol)
            else:
                logger.debug("Screened out: %s", reason)
        return passed
