"""
One-time (or periodic) script to populate the stocks table with the
NIFTY 500 universe. Run via: python scripts/bootstrap_universe.py
or: make bootstrap
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from config.settings import get_settings
from src.data.providers.yahoo import YahooProvider
from src.data.universe import UniverseManager
from src.storage.db import init_db, get_session
from src.storage.repository import StockRepository

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
console = Console()


def main() -> None:
    settings = get_settings()
    console.rule("[bold blue]Investment Intelligence Engine — Universe Bootstrap")

    # 1. Initialise DB
    console.print("[cyan]Initialising database…")
    init_db()
    console.print("[green]✓ Database ready")

    # 2. Fetch universe list from NSE
    yahoo = YahooProvider(request_delay=0.5)
    manager = UniverseManager(yahoo_provider=yahoo)

    console.print("[cyan]Fetching NIFTY 500 list from NSE India…")
    raw_stocks = manager.fetch_universe()
    console.print(f"[green]✓ {len(raw_stocks)} symbols fetched")

    # Limit to configured universe size
    raw_stocks = raw_stocks[: settings.stock_universe_size]

    # 3. Enrich each stock via yfinance
    repo = StockRepository()
    saved = 0
    errors = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Enriching stocks…", total=len(raw_stocks))

        with get_session() as session:
            for raw in raw_stocks:
                progress.update(task, description=f"[cyan]{raw['symbol']}")
                try:
                    enriched = manager.enrich(raw, delay=0.3)
                    repo.upsert(session, enriched)
                    saved += 1
                except Exception as e:
                    logger.warning("Failed to enrich %s: %s", raw["symbol"], e)
                    # Still save with minimal data
                    try:
                        repo.upsert(session, {**raw, "cap_category": "MID", "is_active": True})
                        saved += 1
                    except Exception:
                        errors += 1
                progress.advance(task)

        total_in_db = repo.count(session)

    # 4. Summary
    console.rule("[bold green]Bootstrap Complete")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")
    table.add_row("Symbols processed", str(len(raw_stocks)))
    table.add_row("Saved / updated", str(saved))
    table.add_row("Errors", str(errors))
    table.add_row("Total active in DB", str(total_in_db))
    console.print(table)

    if errors > 0:
        console.print(f"[yellow]⚠  {errors} symbols skipped due to errors")


if __name__ == "__main__":
    main()
