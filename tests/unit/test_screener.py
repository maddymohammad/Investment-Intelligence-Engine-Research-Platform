"""Unit tests for StockScreener fundamental quality gate."""
import pytest
from unittest.mock import MagicMock
from src.selection.screener import StockScreener


@pytest.fixture
def screener():
    settings = MagicMock()
    return StockScreener(settings=settings)


def _fund(symbol="TCS.NS", cap="LARGE", **overrides):
    base = {
        "symbol": symbol,
        "cap_category": cap,
        "current_price": 1500.0,
        "profit_margin": 0.20,
        "debt_to_equity": 0.5,
        "pe_ratio": 25.0,
        "earnings_growth": 0.15,
        "revenue_growth": 0.10,
    }
    base.update(overrides)
    return base


class TestScreenerPasses:
    def test_healthy_large_cap_passes(self, screener):
        ok, reason = screener.passes(_fund(cap="LARGE"), "LARGE")
        assert ok
        assert reason == ""

    def test_healthy_small_cap_passes(self, screener):
        ok, reason = screener.passes(_fund(symbol="XYZ.NS", cap="SMALL"), "SMALL")
        assert ok

    def test_no_price_fails(self, screener):
        ok, reason = screener.passes(_fund(current_price=0), "LARGE")
        assert not ok
        assert "price" in reason.lower()

    def test_none_price_fails(self, screener):
        ok, reason = screener.passes(_fund(current_price=None), "LARGE")
        assert not ok

    def test_loss_making_small_cap_fails(self, screener):
        ok, reason = screener.passes(
            _fund(symbol="SMALL.NS", cap="SMALL", profit_margin=-0.05),
            "SMALL"
        )
        assert not ok
        assert "loss" in reason.lower()

    def test_loss_making_large_cap_passes(self, screener):
        # Large caps get latitude during restructuring
        ok, reason = screener.passes(
            _fund(cap="LARGE", profit_margin=-0.05),
            "LARGE"
        )
        assert ok

    def test_high_debt_fails(self, screener):
        ok, reason = screener.passes(_fund(debt_to_equity=6.0), "LARGE")
        assert not ok
        assert "D/E" in reason or "debt" in reason.lower()

    def test_debt_at_threshold_passes(self, screener):
        ok, _ = screener.passes(_fund(debt_to_equity=5.0), "LARGE")
        assert ok

    def test_extreme_pe_without_growth_fails(self, screener):
        ok, reason = screener.passes(
            _fund(pe_ratio=120.0, earnings_growth=0.10),
            "LARGE"
        )
        assert not ok
        assert "P/E" in reason or "valuation" in reason.lower()

    def test_extreme_pe_with_growth_passes(self, screener):
        ok, _ = screener.passes(
            _fund(pe_ratio=120.0, earnings_growth=0.40),
            "LARGE"
        )
        assert ok

    def test_revenue_shrink_small_cap_fails(self, screener):
        ok, reason = screener.passes(
            _fund(cap="SMALL", revenue_growth=-0.15),
            "SMALL"
        )
        assert not ok
        assert "revenue" in reason.lower()

    def test_minor_revenue_dip_passes(self, screener):
        # -5% is below the -10% threshold
        ok, _ = screener.passes(
            _fund(cap="SMALL", revenue_growth=-0.05),
            "SMALL"
        )
        assert ok


class TestFilterByCap:
    def test_filters_by_cap_category(self, screener):
        fundamentals = {
            "TCS.NS": _fund("TCS.NS", cap="LARGE"),
            "SMALL1.NS": _fund("SMALL1.NS", cap="SMALL"),
            "SMALL2.NS": _fund("SMALL2.NS", cap="SMALL"),
        }
        result = screener.filter_by_cap(fundamentals, "SMALL")
        assert "SMALL1.NS" in result
        assert "SMALL2.NS" in result
        assert "TCS.NS" not in result

    def test_excludes_failing_stocks(self, screener):
        fundamentals = {
            "GOOD.NS": _fund("GOOD.NS", cap="SMALL"),
            "BAD.NS": _fund("BAD.NS", cap="SMALL", current_price=0),
        }
        result = screener.filter_by_cap(fundamentals, "SMALL")
        assert "GOOD.NS" in result
        assert "BAD.NS" not in result

    def test_empty_fundamentals_returns_empty(self, screener):
        assert screener.filter_by_cap({}, "LARGE") == []
