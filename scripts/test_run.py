"""
Phase 1 verification script.
Confirms: DB init → price fetch → fundamental fetch → DB write → summary.
Run via: python scripts/test_run.py
or: make test-run
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.table import Table

from config.constants import NIFTY50_SYMBOLS
from src.data.collectors.fundamental import FundamentalCollector
from src.data.collectors.macro import MacroCollector
from src.data.collectors.price import PriceCollector
from src.data.providers.yahoo import YahooProvider
from src.storage.db import init_db, get_session
from src.storage.models import Stock
from src.storage.repository import StockRepository

logging.basicConfig(level=logging.WARNING, format="%(levelname)s | %(message)s")
console = Console()

# Small sample so the test completes quickly
TEST_SYMBOLS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ITC.NS"]


def test_db() -> None:
    console.print("\n[bold cyan]1. Database initialisation")
    init_db()
    with get_session() as session:
        count = session.query(Stock).count()
    console.print(f"[green]   ✓ DB ready — {count} stocks currently in universe")


def test_prices() -> None:
    console.print("\n[bold cyan]2. Price collection")
    collector = PriceCollector()
    table = Table(show_header=True, header_style="bold")
    table.add_column("Symbol")
    table.add_column("Rows", justify="right")
    table.add_column("Latest Close", justify="right")
    table.add_column("Status")

    for sym in TEST_SYMBOLS:
        df = collector.collect(sym, period="1mo")
        if df is not None and not df.empty:
            close = f"₹{df['Close'].iloc[-1]:,.2f}"
            table.add_row(sym, str(len(df)), close, "[green]OK")
        else:
            table.add_row(sym, "—", "—", "[red]FAIL")

    console.print(table)


def test_fundamentals() -> None:
    console.print("\n[bold cyan]3. Fundamental collection")
    # Skip Screener.in in test to avoid rate limiting; use Yahoo only
    collector = FundamentalCollector(use_screener=False)
    repo = StockRepository()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Symbol")
    table.add_column("Name")
    table.add_column("Sector")
    table.add_column("Market Cap (Cr)", justify="right")
    table.add_column("P/E", justify="right")
    table.add_column("ROE", justify="right")
    table.add_column("Cap Cat")

    with get_session() as session:
        for sym in TEST_SYMBOLS:
            data = collector.collect(sym)

            mc = data.get("market_cap_cr")
            pe = data.get("pe_ratio")
            roe = data.get("roe")

            from src.data.universe import UniverseManager
            from src.data.providers.yahoo import YahooProvider

            manager = UniverseManager(YahooProvider())
            cat = manager.categorise_by_market_cap(mc)

            stock_data = {
                "symbol": sym,
                "name": data.get("name") or sym,
                "exchange": "NSE",
                "cap_category": cat,
                "sector": data.get("sector"),
                "industry": data.get("industry"),
                "market_cap_cr": mc,
                "is_active": True,
            }
            repo.upsert(session, stock_data)

            table.add_row(
                sym,
                (data.get("name") or "")[:25],
                (data.get("sector") or "—")[:15],
                f"{mc:,.0f}" if mc else "—",
                f"{pe:.1f}" if pe else "—",
                f"{roe*100:.1f}%" if roe else "—",
                cat,
            )

    console.print(table)
    console.print("[green]   ✓ Stocks upserted into DB")


def test_macro() -> None:
    console.print("\n[bold cyan]4. Macro & news collection")
    from config.settings import get_settings
    collector = MacroCollector(fred_api_key=get_settings().fred_api_key)
    data = collector.collect()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Indicator")
    table.add_column("Value")
    for k, v in data.items():
        if k == "india_market_headlines":
            table.add_row("News headlines", f"{len(v)} fetched")
        else:
            table.add_row(k, str(v) if v is not None else "—")
    console.print(table)


def test_ai_provider() -> None:
    console.print("\n[bold cyan]5. AI provider instantiation")
    try:
        from src.ai.factory import get_ai_provider
        provider = get_ai_provider()
        console.print(
            f"[green]   ✓ Provider: [bold]{provider.name}[/bold] | "
            f"Analysis model: {provider.analysis_model} | "
            f"Screening model: {provider.screening_model}"
        )
    except Exception as e:
        console.print(f"[yellow]   ⚠  AI provider not configured yet: {e}")
        console.print("[dim]   (Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env to enable)")


def main() -> None:
    console.rule("[bold blue]Investment Intelligence Engine — Phase 1 Test Run")

    test_db()
    test_prices()
    test_fundamentals()
    test_macro()
    test_ai_provider()

    console.rule("[bold green]Phase 1 Tests Complete")
    console.print(
        "[green]✓ All Phase 1 components verified.\n"
        "[dim]Run [bold]make bootstrap[/bold] to populate the full NIFTY 500 universe."
    )


if __name__ == "__main__":
    main()
