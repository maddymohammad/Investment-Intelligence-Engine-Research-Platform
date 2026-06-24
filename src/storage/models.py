from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey,
    Index, Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── Stock universe ───────────────────────────────────────────────

class Stock(Base):
    __tablename__ = "stocks"
    __table_args__ = (
        Index("ix_stocks_cap_category", "cap_category"),
        Index("ix_stocks_sector", "sector"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    exchange: Mapped[str] = mapped_column(String(10), nullable=False)          # NSE | BSE
    cap_category: Mapped[str] = mapped_column(String(10), nullable=False)      # SMALL | MID | LARGE
    sector: Mapped[Optional[str]] = mapped_column(String(100))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    market_cap_cr: Mapped[Optional[float]] = mapped_column(Float)              # Crore INR
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    recommendations: Mapped[list[Recommendation]] = relationship("Recommendation", back_populates="stock")
    analyses: Mapped[list[Analysis]] = relationship("Analysis", back_populates="stock")


# ─── Daily recommendations ────────────────────────────────────────

class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        Index("ix_rec_run_date", "run_date"),
        Index("ix_rec_symbol", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("stocks.symbol"), nullable=False)
    cap_category: Mapped[str] = mapped_column(String(10), nullable=False)      # SMALL | LARGE
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)        # 1 or 2 within category
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    target_price: Mapped[Optional[float]] = mapped_column(Float)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)           # 0.0–1.0
    time_horizon: Mapped[Optional[str]] = mapped_column(String(10))            # SHORT | MEDIUM | LONG
    status: Mapped[str] = mapped_column(String(10), default="OPEN")            # OPEN | CLOSED | EXPIRED
    closed_at: Mapped[Optional[date]] = mapped_column(Date)
    exit_price: Mapped[Optional[float]] = mapped_column(Float)
    return_pct: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    stock: Mapped[Stock] = relationship("Stock", back_populates="recommendations")
    paper_positions: Mapped[list[PaperPosition]] = relationship("PaperPosition", back_populates="recommendation")
    performance: Mapped[list[PerformanceTracking]] = relationship("PerformanceTracking", back_populates="recommendation")


# ─── Full AI analysis per stock per run ───────────────────────────

class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), ForeignKey("stocks.symbol"), nullable=False)

    fundamental_score: Mapped[Optional[float]] = mapped_column(Float)
    technical_score: Mapped[Optional[float]] = mapped_column(Float)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float)
    valuation_score: Mapped[Optional[float]] = mapped_column(Float)
    risk_score: Mapped[Optional[float]] = mapped_column(Float)
    composite_score: Mapped[Optional[float]] = mapped_column(Float)

    bull_case: Mapped[Optional[str]] = mapped_column(Text)
    bear_case: Mapped[Optional[str]] = mapped_column(Text)
    risk_factors: Mapped[Optional[str]] = mapped_column(Text)    # JSON array
    catalysts: Mapped[Optional[str]] = mapped_column(Text)       # JSON array
    analyst_summary: Mapped[Optional[str]] = mapped_column(Text)

    ai_provider: Mapped[Optional[str]] = mapped_column(String(20))
    ai_model: Mapped[Optional[str]] = mapped_column(String(60))
    raw_data: Mapped[Optional[str]] = mapped_column(Text)        # full JSON snapshot

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    stock: Mapped[Stock] = relationship("Stock", back_populates="analyses")


# ─── Daily market macro snapshot ──────────────────────────────────

class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    nifty50_close: Mapped[Optional[float]] = mapped_column(Float)
    sensex_close: Mapped[Optional[float]] = mapped_column(Float)
    nifty50_change_pct: Mapped[Optional[float]] = mapped_column(Float)
    sensex_change_pct: Mapped[Optional[float]] = mapped_column(Float)
    market_breadth: Mapped[Optional[str]] = mapped_column(String(10))  # BULLISH | BEARISH | NEUTRAL
    vix_india: Mapped[Optional[float]] = mapped_column(Float)
    top_sectors: Mapped[Optional[str]] = mapped_column(Text)           # JSON array
    macro_summary: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ─── Per-position daily price tracking ────────────────────────────

class PerformanceTracking(Base):
    __tablename__ = "performance_tracking"
    __table_args__ = (
        Index("ix_perf_rec_id", "recommendation_id"),
        Index("ix_perf_date", "tracking_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[int] = mapped_column(Integer, ForeignKey("recommendations.id"), nullable=False)
    tracking_date: Mapped[date] = mapped_column(Date, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    nifty50_return_pct: Mapped[Optional[float]] = mapped_column(Float)
    sensex_return_pct: Mapped[Optional[float]] = mapped_column(Float)
    alpha: Mapped[Optional[float]] = mapped_column(Float)               # return_pct − nifty50_return_pct
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    recommendation: Mapped[Recommendation] = relationship("Recommendation", back_populates="performance")


# ─── Run audit log ────────────────────────────────────────────────

class RunLog(Base):
    __tablename__ = "run_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)   # SUCCESS | FAILED | PARTIAL
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    stocks_screened: Mapped[Optional[int]] = mapped_column(Integer)
    stocks_selected: Mapped[Optional[int]] = mapped_column(Integer)
    report_path: Mapped[Optional[str]] = mapped_column(String(500))
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    git_commit_sha: Mapped[Optional[str]] = mapped_column(String(40))
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ─── Report file metadata ─────────────────────────────────────────

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    markdown_path: Mapped[Optional[str]] = mapped_column(String(500))
    html_path: Mapped[Optional[str]] = mapped_column(String(500))
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500))
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    email_recipient: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ─── Paper portfolio: individual positions ────────────────────────

class PaperPosition(Base):
    """
    One row per recommendation pick.
    Allocation is always MAX_POSITION_PCT (default 25 %) — never sized up
    when fewer picks are made, so NO RECOMMENDATION days preserve capital.
    """
    __tablename__ = "paper_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recommendation_id: Mapped[int] = mapped_column(Integer, ForeignKey("recommendations.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)

    allocation_pct: Mapped[float] = mapped_column(Float, nullable=False)        # e.g. 0.25
    position_value_inr: Mapped[float] = mapped_column(Float, nullable=False)    # INR value at entry
    shares_hypothetical: Mapped[float] = mapped_column(Float, nullable=False)   # fractional shares

    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[Optional[float]] = mapped_column(Float)
    exit_date: Mapped[Optional[date]] = mapped_column(Date)

    return_pct: Mapped[Optional[float]] = mapped_column(Float)
    holding_days: Mapped[Optional[int]] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(10), default="OPEN")             # OPEN | CLOSED
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    recommendation: Mapped[Recommendation] = relationship("Recommendation", back_populates="paper_positions")


# ─── Paper portfolio: daily portfolio-level snapshot ──────────────

class PortfolioSnapshot(Base):
    """
    One row per calendar day. Computed after market close price update.
    """
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)

    # Valuation
    total_value_inr: Mapped[float] = mapped_column(Float, nullable=False)
    cash_value_inr: Mapped[float] = mapped_column(Float, nullable=False)
    invested_value_inr: Mapped[float] = mapped_column(Float, nullable=False)

    # Returns from inception
    total_return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    nifty50_return_pct: Mapped[Optional[float]] = mapped_column(Float)          # benchmark same period
    sensex_return_pct: Mapped[Optional[float]] = mapped_column(Float)
    alpha: Mapped[Optional[float]] = mapped_column(Float)                       # total_return − nifty50_return

    # Risk metrics
    max_drawdown_pct: Mapped[Optional[float]] = mapped_column(Float)
    current_drawdown_pct: Mapped[Optional[float]] = mapped_column(Float)
    cagr: Mapped[Optional[float]] = mapped_column(Float)
    sharpe_ratio: Mapped[Optional[float]] = mapped_column(Float)

    # Trade stats
    win_rate: Mapped[Optional[float]] = mapped_column(Float)
    total_trades: Mapped[int] = mapped_column(Integer, default=0)
    open_positions: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
