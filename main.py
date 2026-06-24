"""
Investment Intelligence Engine — CLI entrypoint.

RESEARCH & ANALYSIS PLATFORM ONLY.
This system never places trades or connects to brokerage accounts.
See DISCLAIMER.md and src/safeguards.py for the full policy.

Usage:
    python main.py run          # Full daily pipeline
    python main.py status       # Show latest run log
    python main.py bootstrap    # Populate/refresh stock universe
    python main.py analyse      # Run analysis engine on current universe
"""
from __future__ import annotations

import logging

import click
from rich.console import Console

from src.safeguards import RESEARCH_ONLY_NOTICE, assert_research_only

console = Console()


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


@click.group()
@click.option("--log-level", default=None, help="Override LOG_LEVEL env var")
def cli(log_level: str | None) -> None:
    from config.settings import get_settings

    lvl = log_level or get_settings().log_level
    _setup_logging(lvl)
    assert_research_only()
    console.print(RESEARCH_ONLY_NOTICE, style="dim")


@cli.command()
@click.option("--date", "run_date", default=None, help="Override run date (YYYY-MM-DD)")
def run(run_date: str | None) -> None:
    """Execute the full daily pipeline (data → analyse → AI → report → email → commit)."""
    from src.pipeline.daily import run_daily
    import datetime as _dt

    parsed_date = None
    if run_date:
        try:
            parsed_date = _dt.date.fromisoformat(run_date)
        except ValueError:
            console.print(f"[red]Invalid date format: {run_date}. Use YYYY-MM-DD.")
            raise SystemExit(1)

    run_daily(run_date=parsed_date)


@cli.command()
def bootstrap() -> None:
    """Populate / refresh the stock universe from NSE India."""
    from scripts.bootstrap_universe import main as _bootstrap
    _bootstrap()


@cli.command()
def status() -> None:
    """Show the most recent run log entry."""
    from src.storage.db import init_db, get_session
    from src.storage.repository import RunLogRepository

    init_db()
    repo = RunLogRepository()
    with get_session() as session:
        log = repo.get_latest(session)

    if log is None:
        console.print("[yellow]No runs recorded yet.")
        return

    console.print(f"[bold]Last run:[/bold] {log.run_date}")
    console.print(f"  Status:   [{'green' if log.status == 'SUCCESS' else 'red'}]{log.status}")
    console.print(f"  Screened: {log.stocks_screened or '—'}")
    console.print(f"  Selected: {log.stocks_selected or '—'}")
    if log.error_message:
        console.print(f"  Error:    [red]{log.error_message[:120]}")


@cli.command()
@click.argument("symbols", nargs=-1)
@click.option("--top", default=20, show_default=True, help="Number of top stocks to show")
@click.option("--cap", default=None, type=click.Choice(["SMALL", "LARGE"]), help="Filter by cap category")
def analyse(symbols: tuple, top: int, cap: str | None) -> None:
    """Run analysis engine on specific symbols or the full screened universe.

    Examples:
        python main.py analyse                    # Screen and score entire universe
        python main.py analyse TCS.NS INFY.NS     # Analyse specific symbols
        python main.py analyse --cap SMALL --top 10
    """
    import datetime as _dt
    from src.storage.db import init_db, get_session
    from src.storage.repository import StockRepository
    from src.analysis.composer import StockAnalyser
    from src.selection.screener import StockScreener
    from config.settings import get_settings
    from rich.table import Table

    init_db()
    settings = get_settings()
    run_date = _dt.date.today()

    with get_session() as session:
        stocks = StockRepository().get_active(session, cap_category=cap)

    if not stocks:
        console.print("[yellow]No stocks in universe — run 'bootstrap' first.")
        raise SystemExit(1)

    symbol_to_cat = {s.symbol: s.cap_category for s in stocks}

    if symbols:
        target = [s.upper() for s in symbols]
        # Accept bare symbols without .NS suffix
        resolved = []
        for t in target:
            if t in symbol_to_cat:
                resolved.append(t)
            elif f"{t}.NS" in symbol_to_cat:
                resolved.append(f"{t}.NS")
            else:
                console.print(f"[yellow]  {t} not in universe — skipping")
        if not resolved:
            console.print("[red]No valid symbols found.")
            raise SystemExit(1)
        analyse_symbols = resolved
    else:
        analyse_symbols = list(symbol_to_cat.keys())

    console.print(f"[cyan]Building analysis engine…")
    analyser = StockAnalyser.build(fetch_sector=True)

    # Collect fundamentals
    from rich.progress import track
    fundamentals: dict = {}
    for sym in track(analyse_symbols, description="Collecting fundamentals…", transient=True):
        try:
            fd = analyser.fundamentals.collect(sym)
            fd["cap_category"] = symbol_to_cat.get(sym, "LARGE")
            fundamentals[sym] = fd
        except Exception:
            pass

    # Screen (only when analysing full universe, not specific symbols)
    if not symbols:
        screener = StockScreener(settings)
        sm = screener.filter_by_cap(fundamentals, "SMALL")
        lg = screener.filter_by_cap(fundamentals, "LARGE")
        analyse_symbols = list(set(sm + lg))
        console.print(f"[cyan]Screened to {len(analyse_symbols)} candidates")

    # Run analysis
    results = []
    for sym in track(analyse_symbols, description="Analysing…", transient=True):
        try:
            ar = analyser.analyse(sym, run_date=run_date, fund_data=fundamentals.get(sym))
            results.append((sym, ar))
        except Exception as e:
            console.print(f"[yellow]  {sym}: {e}")

    # Sort by composite score
    results.sort(key=lambda x: x[1].composite_score, reverse=True)
    results = results[:top]

    # Display table
    table = Table(title=f"Analysis Results — Top {len(results)} of {len(analyse_symbols)} ({run_date})")
    table.add_column("Symbol", style="bold")
    table.add_column("Cap")
    table.add_column("Score", justify="right")
    table.add_column("Fundamental", justify="right")
    table.add_column("Technical", justify="right")
    table.add_column("Sentiment", justify="right")
    table.add_column("Macro/Risk", justify="right")

    for sym, ar in results:
        score = ar.composite_score
        colour = "green" if score >= 65 else "yellow" if score >= 50 else "red"
        table.add_row(
            sym,
            symbol_to_cat.get(sym, "?"),
            f"[{colour}]{score:.1f}[/{colour}]",
            f"{ar.fundamental_score:.1f}",
            f"{ar.technical_score:.1f}",
            f"{ar.sentiment_score:.1f}",
            f"{ar.macro_risk_score:.1f}",
        )

    console.print(table)


if __name__ == "__main__":
    cli()
