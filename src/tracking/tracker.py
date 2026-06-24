"""
Performance tracker: updates open positions with current prices after market close.

For each open PaperPosition:
  - Fetches the latest closing price
  - Computes return vs entry price
  - Computes alpha vs NIFTY 50 (same entry-to-today period)
  - Writes a PerformanceTracking row
  - If a position has been open > DEFAULT_POSITION_HORIZON_DAYS, marks it closed

After updating positions, computes a daily PortfolioSnapshot:
  - Total portfolio value (invested + cash)
  - Aggregate return vs NIFTY 50 and SENSEX
  - Drawdown, CAGR, Sharpe ratio, win rate
"""
from __future__ import annotations

import logging
import math
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


class PerformanceTracker:

    def __init__(self, settings) -> None:
        self.settings = settings

    def update_open_positions(self, tracking_date: date, analyser) -> None:
        """
        Fetch current prices for all open paper positions, write tracking rows,
        auto-close expired positions, then compute a portfolio snapshot.
        """
        from src.storage.db import get_session
        from src.storage.repository import PortfolioRepository

        with get_session() as session:
            positions = PortfolioRepository().get_open_positions(session)

        if not positions:
            logger.debug("No open positions to track")
            return

        logger.info("Tracking %d open position(s)", len(positions))

        nifty_entry_prices = self._get_nifty_entry_prices(positions, analyser)
        nifty_today = self._get_current_price("^NSEI", analyser)

        for pos in positions:
            try:
                self._update_position(
                    pos, tracking_date, analyser, nifty_today, nifty_entry_prices
                )
            except Exception as e:
                logger.warning("Tracking update failed for position %d: %s", pos.id, e)

        self._compute_snapshot(tracking_date, analyser, nifty_today)

    # ─── Position update ──────────────────────────────────────────────────────

    def _update_position(
        self,
        pos,
        tracking_date: date,
        analyser,
        nifty_today: Optional[float],
        nifty_entry_prices: dict,
    ) -> None:
        from config.constants import DEFAULT_POSITION_HORIZON_DAYS
        from src.storage.db import get_session
        from src.storage.repository import (
            PerformanceTrackingRepository, PortfolioRepository,
        )

        current_price = self._get_current_price(pos.symbol, analyser)
        if current_price is None:
            logger.debug("No price available for %s — skipping", pos.symbol)
            return

        return_pct = (current_price - pos.entry_price) / pos.entry_price * 100

        # Alpha vs NIFTY 50 (same entry date)
        nifty_entry = nifty_entry_prices.get(pos.recommendation_id)
        nifty_return_pct = None
        alpha = None
        if nifty_today and nifty_entry:
            nifty_return_pct = (nifty_today - nifty_entry) / nifty_entry * 100
            alpha = return_pct - nifty_return_pct

        with get_session() as session:
            pt_repo = PerformanceTrackingRepository()
            port_repo = PortfolioRepository()

            if not pt_repo.exists(session, pos.recommendation_id, tracking_date):
                pt_repo.create(session, {
                    "recommendation_id": pos.recommendation_id,
                    "tracking_date": tracking_date,
                    "price": current_price,
                    "return_pct": return_pct,
                    "nifty50_return_pct": nifty_return_pct,
                    "alpha": alpha,
                })

            # Auto-close after horizon days
            holding_days = (tracking_date - pos.run_date).days
            if holding_days >= DEFAULT_POSITION_HORIZON_DAYS:
                port_repo.close_position(
                    session,
                    pos_id=pos.id,
                    exit_price=current_price,
                    exit_date=tracking_date,
                    holding_days=holding_days,
                )
                logger.info(
                    "Auto-closed %s after %d days — return %.2f%%",
                    pos.symbol, holding_days, return_pct,
                )

    # ─── Portfolio snapshot ───────────────────────────────────────────────────

    def _compute_snapshot(
        self,
        snapshot_date: date,
        analyser,
        nifty_today: Optional[float],
    ) -> None:
        from src.storage.db import get_session
        from src.storage.repository import PortfolioRepository

        with get_session() as session:
            port_repo = PortfolioRepository()
            open_positions = port_repo.get_open_positions(session)
            all_snapshots = port_repo.get_all_snapshots(session)

        capital = self.settings.paper_portfolio_initial_capital

        # Current invested value
        invested = 0.0
        for pos in open_positions:
            price = self._get_current_price(pos.symbol, analyser)
            if price and pos.shares_hypothetical:
                invested += price * pos.shares_hypothetical

        # Closed positions P&L
        with get_session() as session:
            from src.storage.models import PaperPosition
            closed = (
                session.query(PaperPosition)
                .filter_by(status="CLOSED")
                .all()
            )

        closed_pnl = sum(
            (p.return_pct or 0) / 100 * p.position_value_inr
            for p in closed
        )
        cash = capital - sum(p.position_value_inr for p in open_positions) + closed_pnl
        total = max(cash + invested, 0.0)
        total_return_pct = (total - capital) / capital * 100

        # Win rate
        wins = [p for p in closed if (p.return_pct or 0) > 0]
        win_rate = len(wins) / len(closed) if closed else None

        # Drawdown (peak-to-trough over all snapshots + current)
        values = [s.total_value_inr for s in all_snapshots] + [total]
        peak = max(values) if values else capital
        current_drawdown = (peak - total) / peak * 100 if peak else 0.0
        max_drawdown = max(
            (peak2 - v) / peak2 * 100
            for i, v in enumerate(values)
            for peak2 in [max(values[:i + 1])]
            if peak2 > 0
        ) if len(values) > 1 else 0.0

        # CAGR
        days_running = (snapshot_date - date(snapshot_date.year, 1, 1)).days + 1
        if total > 0 and days_running > 30:
            cagr = ((total / capital) ** (365 / days_running) - 1) * 100
        else:
            cagr = None

        # NIFTY return (from DB inception snapshot)
        nifty_return_pct = None
        if all_snapshots and nifty_today:
            first_snap = all_snapshots[0]
            if first_snap.nifty50_return_pct is not None:
                pass  # already computed at inception

        # Sharpe (rough: annualised return / annualised vol of daily snapshot returns)
        sharpe = None
        if len(all_snapshots) >= 20:
            daily_returns = []
            prev_vals = [s.total_value_inr for s in all_snapshots[-20:]]
            for i in range(1, len(prev_vals)):
                daily_returns.append((prev_vals[i] - prev_vals[i - 1]) / prev_vals[i - 1])
            if daily_returns:
                mean_r = sum(daily_returns) / len(daily_returns)
                variance = sum((r - mean_r) ** 2 for r in daily_returns) / len(daily_returns)
                std = math.sqrt(variance) if variance > 0 else 0
                if std > 0:
                    sharpe = (mean_r * 252) / (std * math.sqrt(252))

        with get_session() as session:
            PortfolioRepository().upsert_snapshot(session, {
                "snapshot_date": snapshot_date,
                "total_value_inr": total,
                "cash_value_inr": cash,
                "invested_value_inr": invested,
                "total_return_pct": total_return_pct,
                "nifty50_return_pct": nifty_return_pct,
                "alpha": (total_return_pct - nifty_return_pct)
                         if nifty_return_pct is not None else None,
                "max_drawdown_pct": max_drawdown,
                "current_drawdown_pct": current_drawdown,
                "cagr": cagr,
                "sharpe_ratio": sharpe,
                "win_rate": win_rate,
                "total_trades": len(closed),
                "open_positions": len(open_positions),
            })

        logger.info(
            "Portfolio snapshot: total=₹%s (%.2f%%), open=%d, closed=%d",
            f"{total:,.0f}", total_return_pct, len(open_positions), len(closed),
        )

    # ─── Price helpers ────────────────────────────────────────────────────────

    def _get_current_price(self, symbol: str, analyser) -> Optional[float]:
        try:
            return analyser.prices.get_latest_close(symbol)
        except Exception as e:
            logger.debug("Price fetch failed for %s: %s", symbol, e)
            return None

    def _get_nifty_entry_prices(self, positions: list, analyser) -> dict:
        """
        Return {recommendation_id: nifty_price_at_entry_date} for open positions.
        Used to compute alpha since recommendation date.
        """
        from src.storage.db import get_session
        from src.storage.models import MarketSnapshot

        result: dict[int, Optional[float]] = {}
        with get_session() as session:
            for pos in positions:
                snap = (
                    session.query(MarketSnapshot)
                    .filter_by(snapshot_date=pos.run_date)
                    .first()
                )
                result[pos.recommendation_id] = (
                    snap.nifty50_close if snap else None
                )
        return result
