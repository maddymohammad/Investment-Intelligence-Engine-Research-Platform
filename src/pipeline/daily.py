"""
Daily pipeline orchestrator.

Runs after market close (18:00 IST by default):
  1.  Init DB and start run log
  2.  Load active stock universe from DB
  3.  Collect macro data + index prices
  4.  Bulk-collect fundamentals for all universe stocks
  5.  Screen candidates (fundamental quality gate)
  6.  Full analysis on screened candidates only
  7.  Select picks (confidence threshold gate)
  8.  AI deep analysis per selected stock
  9.  Persist recommendations + paper positions to DB
  10. Generate markdown + HTML report
  11. Send email report
  12. Commit report to GitHub
  13. Update performance tracking for open positions
  14. Save market snapshot
  15. Close run log
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Optional

from rich.console import Console
from rich.progress import track

logger = logging.getLogger(__name__)
console = Console()


class DailyPipeline:

    def __init__(self, run_date: Optional[date] = None) -> None:
        from config.settings import get_settings
        self.settings = get_settings()
        self.run_date = run_date or date.today()

    # ─── Public entry point ───────────────────────────────────────────────────

    def run(self) -> list:
        """Execute the full pipeline. Returns list of StockRecommendation."""
        from src.storage.db import get_session, init_db
        from src.storage.repository import RunLogRepository

        init_db()
        start_time = datetime.utcnow()
        log_id: Optional[int] = None

        with get_session() as session:
            log = RunLogRepository().create(session, self.run_date, start_time)
            log_id = log.id

        console.rule(f"[bold blue]Investment Intelligence Engine — {self.run_date}")

        try:
            recs = self._execute(log_id)
            self._update_log(
                log_id,
                status="SUCCESS",
                end_time=datetime.utcnow(),
                stocks_selected=len(recs),
            )
            console.print(
                f"[green bold]✓ Daily run complete — {len(recs)} recommendation(s)"
            )
            return recs
        except Exception as exc:
            logger.exception("Pipeline failed: %s", exc)
            self._update_log(
                log_id,
                status="FAILED",
                end_time=datetime.utcnow(),
                error_message=str(exc)[:500],
            )
            console.print(f"[red bold]✗ Pipeline failed: {exc}")
            raise

    # ─── Main execution ───────────────────────────────────────────────────────

    def _execute(self, log_id: Optional[int]) -> list:
        from src.storage.db import get_session
        from src.storage.repository import AnalysisRepository, StockRepository

        # ── 1. Load universe ───────────────────────────────────────
        with get_session() as session:
            stocks = StockRepository().get_active(session)

        if not stocks:
            console.print("[yellow]No stocks in universe — run 'bootstrap' first.")
            return []

        symbol_to_cat = {s.symbol: s.cap_category for s in stocks}
        symbols = list(symbol_to_cat.keys())
        self._update_log(log_id, stocks_screened=len(symbols))
        console.print(f"[cyan]Universe: {len(symbols)} active stocks")

        # ── 2. Macro + index prices ────────────────────────────────
        macro = self._collect_macro()

        # ── 3. Build analysis engine ───────────────────────────────
        from src.analysis.composer import StockAnalyser
        console.print("[cyan]Initialising analysis engine (fetching sector data)…")
        analyser = StockAnalyser.build(fetch_sector=True)

        # ── 4. Bulk fundamental collection ─────────────────────────
        console.print(f"[cyan]Collecting fundamentals for {len(symbols)} stocks…")
        fundamentals: dict[str, dict] = {}
        for sym in track(symbols, description="Fundamentals…", transient=True):
            try:
                fd = analyser.fundamentals.collect(sym)
                fd["cap_category"] = symbol_to_cat.get(sym, "LARGE")
                fundamentals[sym] = fd
            except Exception as e:
                logger.warning("Fundamental collection failed for %s: %s", sym, e)

        console.print(f"[cyan]Fundamentals collected for {len(fundamentals)} stocks")

        # ── 5. Screen candidates ───────────────────────────────────
        from src.selection.screener import StockScreener
        screener = StockScreener(self.settings)
        sm = screener.filter_by_cap(fundamentals, "SMALL")
        lg = screener.filter_by_cap(fundamentals, "LARGE")
        candidates = list(set(sm + lg))
        console.print(
            f"[cyan]Screened candidates: {len(candidates)} "
            f"({len(sm)} small-cap, {len(lg)} large-cap)"
        )

        # ── 6. Full analysis on screened candidates ────────────────
        analyses: dict = {}
        for sym in track(candidates, description="Analysing…", transient=True):
            try:
                ar = analyser.analyse(
                    sym,
                    run_date=self.run_date,
                    fund_data=fundamentals.get(sym),
                )
                analyses[sym] = ar
            except Exception as e:
                logger.warning("Analysis failed for %s: %s", sym, e)

        console.print(f"[cyan]Analysis complete: {len(analyses)}/{len(candidates)}")

        # ── 7. Selection ───────────────────────────────────────────
        from src.selection.selector import select_stocks
        selection = select_stocks(analyses, fundamentals, run_date=self.run_date)

        # ── 8. Save all analyses to DB ─────────────────────────────
        with get_session() as session:
            for sym, ar in analyses.items():
                try:
                    AnalysisRepository().create(session, ar.to_db_dict())
                except Exception as e:
                    logger.debug("Analysis DB save skipped for %s: %s", sym, e)

        if not selection.has_recommendations:
            console.print(
                f"[yellow]NO PICKS today: {selection.no_recommendation_reason}"
            )
            self._save_market_snapshot(macro)
            self._update_performance(analyser)
            return []

        all_picks = selection.all_picks
        console.print(
            f"[green]Selected: {[p.symbol for p in all_picks]}"
        )

        # ── 9. AI deep analysis per pick ───────────────────────────
        from src.recommendation.builder import build_pre_ai_recommendation
        from src.ai.analyst import analyse_stock

        news = macro.get("india_market_headlines", [])
        recommendations = []

        for pick in all_picks:
            console.print(f"[cyan]  AI deep analysis: {pick.symbol}…")
            ar = analyses[pick.symbol]
            fd = fundamentals.get(pick.symbol, {})
            pre_rec = build_pre_ai_recommendation(
                ar, fd,
                news_headlines=news,
                sector_performance=analyser.sector_performance,
                run_date=self.run_date,
            )
            full_rec = analyse_stock(pre_rec, fd)
            recommendations.append(full_rec)

        # ── 10. Persist recommendations ────────────────────────────
        self._save_recommendations(recommendations)

        # ── 11. Generate report ────────────────────────────────────
        market_ctx = {
            "nifty50_close": macro.get("nifty50_close"),
            "nifty50_change_pct": macro.get("nifty50_change_pct"),
            "sensex_close": macro.get("sensex_close"),
            "sensex_change_pct": macro.get("sensex_change_pct"),
            "headlines": news[:6],
            "fed_funds_rate": macro.get("fed_funds_rate"),
            "wti_crude_usd": macro.get("wti_crude_usd"),
        }
        report_path = self._generate_report(recommendations, market_ctx)
        if report_path:
            self._save_report_record(report_path, len(recommendations))
            self._update_log(log_id, report_path=report_path)

        # ── 12. Email ──────────────────────────────────────────────
        self._send_email(recommendations, report_path)

        # ── 13. GitHub commit ──────────────────────────────────────
        git_sha = self._commit_github(report_path)
        if git_sha:
            self._update_log(log_id, git_commit_sha=git_sha)

        # ── 14. Market snapshot + tracking ────────────────────────
        self._save_market_snapshot(macro)
        self._update_performance(analyser)

        return recommendations

    # ─── Step helpers ─────────────────────────────────────────────────────────

    def _collect_macro(self) -> dict:
        from src.data.collectors.macro import MacroCollector
        from src.data.collectors.price import PriceCollector
        from config.constants import NIFTY50_INDEX, SENSEX_INDEX

        console.print("[cyan]Collecting macro data…")
        mac = MacroCollector(fred_api_key=self.settings.fred_api_key)
        data = mac.collect()

        try:
            pc = PriceCollector()
            for ticker, key_close, key_chg in [
                (NIFTY50_INDEX, "nifty50_close", "nifty50_change_pct"),
                (SENSEX_INDEX, "sensex_close", "sensex_change_pct"),
            ]:
                df = pc.collect(ticker, period="5d")
                if df is not None and len(df) >= 2:
                    data[key_close] = float(df["Close"].iloc[-1])
                    data[key_chg] = float(
                        (df["Close"].iloc[-1] / df["Close"].iloc[-2] - 1) * 100
                    )
        except Exception as e:
            logger.warning("Index price fetch failed: %s", e)

        return data

    def _save_recommendations(self, recommendations: list) -> None:
        from src.storage.db import get_session
        from src.storage.repository import PortfolioRepository, RecommendationRepository

        with get_session() as session:
            rec_repo = RecommendationRepository()
            port_repo = PortfolioRepository()
            for i, rec in enumerate(recommendations, start=1):
                try:
                    saved = rec_repo.create(session, {
                        "run_date": rec.run_date,
                        "symbol": rec.symbol,
                        "cap_category": rec.cap_category,
                        "rank_position": i,
                        "entry_price": rec.entry_price,
                        "confidence_score": rec.confidence_score,
                        "time_horizon": "MEDIUM",
                        "status": "OPEN",
                    })
                    alloc = self.settings.paper_portfolio_max_position_pct
                    capital = self.settings.paper_portfolio_initial_capital
                    port_repo.create_position(session, {
                        "recommendation_id": saved.id,
                        "symbol": rec.symbol,
                        "run_date": rec.run_date,
                        "allocation_pct": alloc,
                        "position_value_inr": capital * alloc,
                        "shares_hypothetical": (
                            (capital * alloc) / rec.entry_price
                            if rec.entry_price else 0.0
                        ),
                        "entry_price": rec.entry_price,
                        "status": "OPEN",
                    })
                except Exception as e:
                    logger.error("DB save failed for %s: %s", rec.symbol, e)

    def _generate_report(
        self, recommendations: list, market_ctx: dict
    ) -> Optional[str]:
        try:
            from src.reports.generator import ReportGenerator
            path = ReportGenerator(self.settings).generate(
                recommendations, self.run_date, market_ctx
            )
            console.print(f"[green]  Report: {path}")
            return path
        except Exception as e:
            logger.error("Report generation failed: %s", e)
            return None

    def _save_report_record(self, report_path: str, rec_count: int) -> None:
        from src.storage.db import get_session
        from src.storage.repository import ReportRepository
        try:
            with get_session() as session:
                ReportRepository().upsert(session, {
                    "run_date": self.run_date,
                    "markdown_path": report_path,
                })
        except Exception as e:
            logger.warning("Report record save failed: %s", e)

    def _send_email(
        self, recommendations: list, report_path: Optional[str]
    ) -> None:
        if not self.settings.email_recipient:
            return
        try:
            from src.email.sender import EmailSender
            sent = EmailSender(self.settings).send_report(
                recommendations, report_path, self.run_date
            )
            if sent:
                console.print("[green]  Email sent")
            else:
                console.print("[yellow]  Email skipped (not configured)")
        except Exception as e:
            logger.warning("Email failed: %s", e)

    def _commit_github(self, report_path: Optional[str]) -> Optional[str]:
        if not report_path or not self.settings.github_token:
            return None
        try:
            from src.git.committer import GitCommitter
            sha = GitCommitter(self.settings).commit_report(report_path, self.run_date)
            if sha:
                console.print(f"[green]  GitHub commit: {sha[:8]}")
            return sha
        except Exception as e:
            logger.warning("GitHub commit failed: %s", e)
            return None

    def _save_market_snapshot(self, macro: dict) -> None:
        from src.storage.db import get_session
        from src.storage.repository import MarketSnapshotRepository

        try:
            with get_session() as session:
                MarketSnapshotRepository().upsert(session, {
                    "snapshot_date": self.run_date,
                    "nifty50_close": macro.get("nifty50_close"),
                    "sensex_close": macro.get("sensex_close"),
                    "nifty50_change_pct": macro.get("nifty50_change_pct"),
                    "sensex_change_pct": macro.get("sensex_change_pct"),
                    "macro_summary": json.dumps({
                        k: v for k, v in macro.items()
                        if k != "india_market_headlines"
                    }),
                })
        except Exception as e:
            logger.warning("Market snapshot save failed: %s", e)

    def _update_performance(self, analyser) -> None:
        try:
            from src.tracking.tracker import PerformanceTracker
            PerformanceTracker(self.settings).update_open_positions(
                self.run_date, analyser
            )
        except Exception as e:
            logger.warning("Performance tracking failed: %s", e)

    def _update_log(self, log_id: Optional[int], **kwargs) -> None:
        if log_id is None:
            return
        from src.storage.db import get_session
        from src.storage.repository import RunLogRepository
        try:
            with get_session() as session:
                RunLogRepository().update(session, log_id, **kwargs)
        except Exception as e:
            logger.debug("Log update failed: %s", e)


def run_daily(run_date: Optional[date] = None) -> list:
    """Convenience function: create and execute a DailyPipeline."""
    return DailyPipeline(run_date).run()
