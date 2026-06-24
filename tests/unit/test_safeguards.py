"""Unit tests for the research-only safeguards module."""
import pytest
from src.safeguards import (
    TradingProhibitedError,
    assert_no_brokerage,
    assert_no_trading_action,
    validate_url,
)


class TestBrokerageBlock:
    def test_blocks_zerodha(self):
        with pytest.raises(TradingProhibitedError):
            assert_no_brokerage("zerodha_client")

    def test_blocks_kite(self):
        with pytest.raises(TradingProhibitedError):
            assert_no_brokerage("kite_connect")

    def test_blocks_groww(self):
        with pytest.raises(TradingProhibitedError):
            assert_no_brokerage("groww_api")

    def test_blocks_upstox(self):
        with pytest.raises(TradingProhibitedError):
            assert_no_brokerage("upstox_sdk")

    def test_allows_yfinance(self):
        # Should not raise — data provider, not brokerage
        assert_no_brokerage("yfinance_provider")

    def test_allows_fred(self):
        assert_no_brokerage("fred_macro_api")

    def test_case_insensitive(self):
        with pytest.raises(TradingProhibitedError):
            assert_no_brokerage("ZERODHA_CONNECTION")


class TestTradingActionBlock:
    def test_blocks_place_order(self):
        with pytest.raises(TradingProhibitedError):
            assert_no_trading_action("place_order")

    def test_blocks_buy_stock(self):
        with pytest.raises(TradingProhibitedError):
            assert_no_trading_action("buy_stock")

    def test_blocks_sell_stock(self):
        with pytest.raises(TradingProhibitedError):
            assert_no_trading_action("sell_stock")

    def test_blocks_execute_trade(self):
        with pytest.raises(TradingProhibitedError):
            assert_no_trading_action("execute_trade")

    def test_allows_analyse(self):
        assert_no_trading_action("analyse_stock")

    def test_allows_generate_report(self):
        assert_no_trading_action("generate_report")


class TestUrlValidation:
    def test_blocks_brokerage_urls(self):
        with pytest.raises(TradingProhibitedError):
            validate_url("https://api.kite.zerodha.com/orders")

    def test_allows_yahoo_finance(self):
        validate_url("https://query1.finance.yahoo.com/v8/finance/chart/TCS.NS")

    def test_allows_fred(self):
        validate_url("https://api.stlouisfed.org/fred/series")
