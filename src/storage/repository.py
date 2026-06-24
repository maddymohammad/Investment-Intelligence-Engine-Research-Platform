from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from .models import (
    PortfolioSnapshot, RunLog, Stock,
    Recommendation, Analysis, PaperPosition,
    MarketSnapshot, Report,
)

logger = logging.getLogger(__name__)


# ─── Stock repository ─────────────────────────────────────────────

class StockRepository:

    def upsert(self, session: Session, data: dict) -> Stock:
        """Insert or update a stock by symbol."""
        existing = session.query(Stock).filter_by(symbol=data["symbol"]).first()
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            return existing
        stock = Stock(**data)
        session.add(stock)
        return stock

    def get_active(self, session: Session, cap_category: Optional[str] = None) -> list[Stock]:
        q = session.query(Stock).filter_by(is_active=True)
        if cap_category:
            q = q.filter_by(cap_category=cap_category)
        return q.all()

    def get_by_symbol(self, session: Session, symbol: str) -> Optional[Stock]:
        return session.query(Stock).filter_by(symbol=symbol).first()

    def count(self, session: Session) -> int:
        return session.query(Stock).filter_by(is_active=True).count()


# ─── Recommendation repository ────────────────────────────────────

class RecommendationRepository:

    def create(self, session: Session, data: dict) -> Recommendation:
        rec = Recommendation(**data)
        session.add(rec)
        session.flush()
        return rec

    def get_by_date(self, session: Session, run_date: date) -> list[Recommendation]:
        return session.query(Recommendation).filter_by(run_date=run_date).all()

    def get_open(self, session: Session) -> list[Recommendation]:
        return session.query(Recommendation).filter_by(status="OPEN").all()

    def close(self, session: Session, rec_id: int, exit_price: float, closed_at: date) -> None:
        rec = session.query(Recommendation).filter_by(id=rec_id).first()
        if rec:
            rec.status = "CLOSED"
            rec.exit_price = exit_price
            rec.closed_at = closed_at
            rec.return_pct = ((exit_price - rec.entry_price) / rec.entry_price) * 100


# ─── Analysis repository ──────────────────────────────────────────

class AnalysisRepository:

    def create(self, session: Session, data: dict) -> Analysis:
        analysis = Analysis(**data)
        session.add(analysis)
        return analysis

    def get_by_date_and_symbol(
        self, session: Session, run_date: date, symbol: str
    ) -> Optional[Analysis]:
        return (
            session.query(Analysis)
            .filter_by(run_date=run_date, symbol=symbol)
            .first()
        )


# ─── Run log repository ───────────────────────────────────────────

class RunLogRepository:

    def create(self, session: Session, run_date: date, start_time) -> RunLog:
        log = RunLog(run_date=run_date, status="RUNNING", start_time=start_time)
        session.add(log)
        session.flush()
        return log

    def update(self, session: Session, log_id: int, **kwargs) -> None:
        log = session.query(RunLog).filter_by(id=log_id).first()
        if log:
            for k, v in kwargs.items():
                setattr(log, k, v)

    def get_latest(self, session: Session) -> Optional[RunLog]:
        return (
            session.query(RunLog)
            .order_by(RunLog.created_at.desc())
            .first()
        )


# ─── Paper portfolio repository ───────────────────────────────────

class PortfolioRepository:

    def create_position(self, session: Session, data: dict) -> PaperPosition:
        pos = PaperPosition(**data)
        session.add(pos)
        session.flush()
        return pos

    def get_open_positions(self, session: Session) -> list[PaperPosition]:
        return session.query(PaperPosition).filter_by(status="OPEN").all()

    def close_position(
        self,
        session: Session,
        pos_id: int,
        exit_price: float,
        exit_date: date,
        holding_days: int,
    ) -> None:
        pos = session.query(PaperPosition).filter_by(id=pos_id).first()
        if pos:
            pos.exit_price = exit_price
            pos.exit_date = exit_date
            pos.holding_days = holding_days
            pos.return_pct = ((exit_price - pos.entry_price) / pos.entry_price) * 100
            pos.status = "CLOSED"

    def upsert_snapshot(self, session: Session, data: dict) -> PortfolioSnapshot:
        existing = (
            session.query(PortfolioSnapshot)
            .filter_by(snapshot_date=data["snapshot_date"])
            .first()
        )
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            return existing
        snap = PortfolioSnapshot(**data)
        session.add(snap)
        return snap

    def get_all_snapshots(self, session: Session) -> list[PortfolioSnapshot]:
        return (
            session.query(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.snapshot_date)
            .all()
        )


# ─── Market snapshot repository ───────────────────────────────────

class MarketSnapshotRepository:

    def upsert(self, session: Session, data: dict) -> MarketSnapshot:
        existing = (
            session.query(MarketSnapshot)
            .filter_by(snapshot_date=data["snapshot_date"])
            .first()
        )
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            return existing
        snap = MarketSnapshot(**data)
        session.add(snap)
        return snap


# ─── Report repository ────────────────────────────────────────────

class ReportRepository:

    def upsert(self, session: Session, data: dict) -> Report:
        existing = (
            session.query(Report)
            .filter_by(run_date=data["run_date"])
            .first()
        )
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            return existing
        report = Report(**data)
        session.add(report)
        return report

    def get_by_date(self, session: Session, run_date: date) -> Optional[Report]:
        return session.query(Report).filter_by(run_date=run_date).first()


# ─── Performance tracking repository ─────────────────────────────

class PerformanceTrackingRepository:
    from .models import PerformanceTracking

    def create(self, session: Session, data: dict):
        from .models import PerformanceTracking
        pt = PerformanceTracking(**data)
        session.add(pt)
        return pt

    def get_by_recommendation(
        self, session: Session, recommendation_id: int
    ) -> list:
        from .models import PerformanceTracking
        return (
            session.query(PerformanceTracking)
            .filter_by(recommendation_id=recommendation_id)
            .order_by(PerformanceTracking.tracking_date)
            .all()
        )

    def exists(
        self, session: Session, recommendation_id: int, tracking_date: date
    ) -> bool:
        from .models import PerformanceTracking
        return (
            session.query(PerformanceTracking)
            .filter_by(
                recommendation_id=recommendation_id,
                tracking_date=tracking_date,
            )
            .first()
        ) is not None
