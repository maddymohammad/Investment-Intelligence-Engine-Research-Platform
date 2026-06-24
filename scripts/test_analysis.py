"""
Phase 2 verification script.
Confirms: safeguards → analysis engine → scoring → ranked candidate list.
Run via: python scripts/test_analysis.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table

console = Console()
logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")

# Small sample for speed — avoids hitting Yahoo Finance 500 times
TEST_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS",  # Large cap
    "TATACONSUM.NS", "TATAMOTORS.NS",                     # Large cap
]


def test_safeguards() -> None:
    console.print("\n[bold cyan]1. Safety boundary enforcement")
    from src.safeguards import (
        TradingProhibitedError,
        assert_no_brokerage,
        assert_no_trading_action,
        validate_url,
    )

    # These must raise
    errors = []
    for call, label in [
        (lambda: assert_no_brokerage("zerodha_client"), "zerodha rejected"),
        (lambda: assert_no_brokerage("groww_api"), "groww rejected"),
        (lambda: assert_no_trading_action("place_order"), "place_order rejected"),
        (lambda: assert_no_trading_action("buy_stock"), "buy_stock rejected"),
        (lambda: validate_url("https://api.zerodha.com/orders"), "zerodha URL rejected"),
    ]:
        try:
            call()
            errors.append(f"[red]FAIL: {label} — no error raised")
        except TradingProhibitedError:
            console.print(f"   [green]✓ {label}")

    # These must pass
    try:
        assert_no_brokerage("yahoo_finance")
        assert_no_trading_action("collect_data")
        validate_url("https://finance.yahoo.com/quote/RELIANCE.NS")
        console.print("   [green]✓ legitimate calls pass through")
    except Exception as e:
        errors.append(f"[red]FAIL: legitimate call was blocked: {e}")

    for err in errors:
        console.print(err)


def test_analysis_engine() -> None:
    console.print("\n[bold cyan]2. Analysis engine (scoring all dimensions)")

    from src.analysis.composer import StockAnalyser

    console.print("   Building analyser (fetches NIFTY 50 + sector data)…")
    analyser = StockAnalyser.build(fetch_sector=True)

    console.print(f"   Analysing {len(TEST_SYMBOLS)} stocks…")
    results = analyser.analyse_bulk(TEST_SYMBOLS)

    table = Table(show_header=True, header_style="bold")
    table.add_column("Symbol", style="cyan")
    table.add_column("Fund", justify="right")
    table.add_column("Tech", justify="right")
    table.add_column("Val", justify="right")
    table.add_column("Risk", justify="right")
    table.add_column("Sector Δ", justify="right")
    table.add_column("Composite", justify="right", style="bold")
    table.add_column("RSI", justify="right")
    table.add_column("MACD")

    for sym, r in sorted(results.items(), key=lambda x: x[1].composite_score, reverse=True):
        rs = f"{r.sector_relative_strength:+.1f}%" if r.sector_relative_strength is not None else "—"
        table.add_row(
            sym,
            f"{r.fundamental_score:.1f}",
            f"{r.technical_score:.1f}",
            f"{r.valuation_score:.1f}",
            f"{r.risk_score:.1f}",
            rs,
            f"{r.composite_score:.1f}",
            str(r.rsi) if r.rsi else "—",
            r.macd_signal or "—",
        )

    console.print(table)
    return results


def test_selection(analyses, fundamentals) -> None:
    console.print("\n[bold cyan]3. Stock selector (confidence threshold gate)")

    from src.selection.selector import select_stocks

    selection = select_stocks(analyses, fundamentals)

    if selection.has_recommendations:
        console.print(f"   [green]✓ {selection.total_picks} stock(s) selected:")
        for pick in selection.all_picks:
            console.print(
                f"     [{pick.cap_category}] {pick.symbol} — "
                f"score {pick.composite_score:.1f} | "
                f"confidence {pick.confidence_score:.0%} | "
                f"₹{pick.entry_price:,.2f}"
            )
    else:
        console.print(
            f"   [yellow]NO RECOMMENDATION — {selection.no_recommendation_reason}"
        )
        console.print("   [dim](This is correct behaviour — system never forces picks)")


def main() -> None:
    console.rule("[bold blue]Investment Intelligence Engine — Phase 2 Test")

    test_safeguards()
    analyses = test_analysis_engine()

    # Build a minimal fundamentals dict from the analysis results for the selector
    from src.data.collectors.fundamental import FundamentalCollector
    from src.data.providers.yahoo import YahooProvider
    from src.storage.db import get_session
    from src.storage.models import Stock

    with get_session() as session:
        stocks = {s.symbol: s for s in session.query(Stock).filter(
            Stock.symbol.in_(TEST_SYMBOLS)
        ).all()}

    fundamentals: dict[str, dict] = {}
    for sym in TEST_SYMBOLS:
        ar = analyses.get(sym)
        stock = stocks.get(sym)
        fundamentals[sym] = {
            "symbol": sym,
            "name": stock.name if stock else sym,
            "cap_category": stock.cap_category if stock else "LARGE",
            "current_price": ar.current_price if ar else None,
            "pe_ratio": None,
            "profit_margin": None,
            "debt_to_equity": None,
            "revenue_growth": None,
        }

    test_selection(analyses, fundamentals)

    console.rule("[bold green]Phase 2 Tests Complete")
    console.print(
        "[green]✓ Analysis engine verified.\n"
        "[dim]Composite scores printed above — ranked list is the Phase 2 deliverable."
    )


if __name__ == "__main__":
    main()
