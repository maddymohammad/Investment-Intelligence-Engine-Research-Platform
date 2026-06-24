"""
Recommendation data model — the canonical output of the AI analysis layer.

Every StockRecommendation contains all 10 mandatory sections defined in
the reporting specification.  The research-only disclaimer is non-optional
and is enforced via __post_init__ on ResearchGuidance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

# ─── Immutable policy disclaimer ─────────────────────────────────────────────

RESEARCH_DISCLAIMER = (
    "RESEARCH & ANALYSIS PURPOSES ONLY — NOT INVESTMENT ADVICE.\n"
    "All price levels, zones, and metrics below are informational and for "
    "personal monitoring only. They are not buy/sell signals, trading "
    "instructions, or recommendations to execute any order. "
    "Actual investment decisions and all order execution remain entirely "
    "the responsibility of the investor. "
    "Past simulated performance does not guarantee future results."
)


# ─── Section 1: Technical Analysis ───────────────────────────────────────────

@dataclass
class TechnicalSummary:
    # RSI
    rsi: Optional[float] = None
    rsi_interpretation: str = ""         # AI narrative

    # MACD
    macd_status: str = ""                # BULLISH | BEARISH | NEUTRAL
    macd_trend: str = ""                 # AI narrative

    # Moving averages
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ma_analysis: str = ""                # AI narrative of price vs MAs

    # Levels (computed by src/analysis/technical.py)
    support_levels: list[float] = field(default_factory=list)
    resistance_levels: list[float] = field(default_factory=list)

    # Volume
    volume_ratio_5d_vs_20d: Optional[float] = None
    volume_trend: str = ""               # AI narrative

    # Composite signal
    adx: Optional[float] = None
    overall_technical_signal: str = ""   # STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL


# ─── Section 2: Fundamental Analysis ─────────────────────────────────────────

@dataclass
class FundamentalSummary:
    # Raw metrics (populated by FundamentalCollector)
    revenue_growth_pct: Optional[float] = None
    eps_growth_pct: Optional[float] = None
    roe_pct: Optional[float] = None
    roce_pct: Optional[float] = None
    debt_to_equity: Optional[float] = None
    profit_margin_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None
    pe_ratio: Optional[float] = None
    peg_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    free_cashflow: Optional[float] = None

    # Sector context
    sector: Optional[str] = None
    sector_avg_pe: Optional[float] = None
    sector_relative_strength_pct: Optional[float] = None

    # AI narratives (one per metric group)
    revenue_growth_interpretation: str = ""
    eps_growth_interpretation: str = ""
    roe_interpretation: str = ""
    roce_interpretation: str = ""
    debt_assessment: str = ""
    margin_assessment: str = ""
    valuation_assessment: str = ""
    sector_comparison: str = ""          # how this stock compares to sector peers


# ─── Section 3: News & Catalysts ─────────────────────────────────────────────

@dataclass
class NewsCatalysts:
    positive_developments: list[str] = field(default_factory=list)
    negative_developments: list[str] = field(default_factory=list)
    upcoming_earnings: Optional[str] = None    # "Q3 FY25 results expected ~Jan 25"
    major_events: list[str] = field(default_factory=list)
    sector_catalysts: list[str] = field(default_factory=list)
    macro_factors: list[str] = field(default_factory=list)


# ─── Section 4: Risk Analysis ─────────────────────────────────────────────────

@dataclass
class RiskAnalysis:
    bear_case: str = ""
    sector_risks: list[str] = field(default_factory=list)
    company_risks: list[str] = field(default_factory=list)
    valuation_risks: list[str] = field(default_factory=list)
    technical_risks: list[str] = field(default_factory=list)
    volatility_assessment: str = ""

    # Quantitative risk data (from risk scorer)
    beta: Optional[float] = None
    volatility_annual_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None


# ─── Section 5: Confidence Score ──────────────────────────────────────────────

@dataclass
class ConfidenceDetail:
    score: float = 0.0            # 0–100 (AI assigns; validated against composite)
    explanation: str = ""         # Paragraph explaining the score
    key_positives: list[str] = field(default_factory=list)   # exactly 3
    key_negatives: list[str] = field(default_factory=list)   # exactly 3


# ─── Section 6: Investment Horizon ────────────────────────────────────────────

@dataclass
class InvestmentHorizon:
    short_term: str = ""     # 1–4 weeks outlook
    medium_term: str = ""    # 1–6 months outlook
    long_term: str = ""      # 6–24 months outlook


# ─── Section 7: Selection Justification ───────────────────────────────────────

@dataclass
class SelectionJustification:
    why_selected: str = ""                                           # over competing opportunities
    bull_reasons: list[str] = field(default_factory=list)           # top 3
    bear_reasons: list[str] = field(default_factory=list)           # top 3
    key_assumptions: list[str] = field(default_factory=list)


# ─── Section 8: Research-Only Guidance ────────────────────────────────────────

@dataclass
class ResearchGuidance:
    """
    Informational price levels for personal watchlist tracking.
    The disclaimer is non-negotiable and enforced in __post_init__.
    """
    watchlist_entry_zone: str = ""       # e.g. "₹1,400 – ₹1,450"
    monitoring_levels: list[str] = field(default_factory=list)
    profit_taking_zones: list[str] = field(default_factory=list)
    stop_loss_zone: str = ""             # e.g. "below ₹1,300"
    disclaimer: str = RESEARCH_DISCLAIMER

    def __post_init__(self) -> None:
        # Guarantee disclaimer is always the canonical text
        if not self.disclaimer:
            self.disclaimer = RESEARCH_DISCLAIMER


# ─── Full Recommendation (all 10 sections) ────────────────────────────────────

@dataclass
class StockRecommendation:
    """
    Complete per-stock recommendation produced by the AI analysis layer.

    Sections 1–8 are populated by the AI analyst.
    Section 9 (historical tracking) is satisfied by the DB models
      (RecommendationDetail, PerformanceTracking, PortfolioSnapshot).
    Section 10 (delivery channels) is satisfied by the report builder,
      email sender, and Streamlit dashboard.
    """
    # ── Identity ──────────────────────────────────────────────────
    symbol: str = ""
    name: str = ""
    cap_category: str = ""         # SMALL | LARGE
    run_date: Optional[date] = None

    # ── Composite scores ──────────────────────────────────────────
    composite_score: float = 0.0
    confidence_score: float = 0.0  # 0.0–1.0 (mirrors confidence.score / 100)
    fundamental_score: float = 50.0
    technical_score: float = 50.0
    valuation_score: float = 50.0
    risk_score: float = 50.0

    # ── Entry price ───────────────────────────────────────────────
    entry_price: float = 0.0

    # ── 8 mandatory AI-generated sections ─────────────────────────
    technical: TechnicalSummary = field(default_factory=TechnicalSummary)
    fundamental: FundamentalSummary = field(default_factory=FundamentalSummary)
    catalysts: NewsCatalysts = field(default_factory=NewsCatalysts)
    risk: RiskAnalysis = field(default_factory=RiskAnalysis)
    confidence: ConfidenceDetail = field(default_factory=ConfidenceDetail)
    horizon: InvestmentHorizon = field(default_factory=InvestmentHorizon)
    justification: SelectionJustification = field(default_factory=SelectionJustification)
    guidance: ResearchGuidance = field(default_factory=ResearchGuidance)

    # ── AI provenance ─────────────────────────────────────────────
    ai_provider: str = ""
    ai_model: str = ""
    generated_at: Optional[datetime] = None

    def to_db_dict(self) -> dict:
        """Serialize to the dict shape expected by RecommendationDetailRepository."""
        import json
        from dataclasses import asdict
        return {
            "technical_json": json.dumps(asdict(self.technical)),
            "fundamental_json": json.dumps(asdict(self.fundamental)),
            "catalysts_json": json.dumps(asdict(self.catalysts)),
            "risk_json": json.dumps(asdict(self.risk)),
            "confidence_score": self.confidence.score,
            "confidence_explanation": self.confidence.explanation,
            "confidence_positives_json": json.dumps(self.confidence.key_positives),
            "confidence_negatives_json": json.dumps(self.confidence.key_negatives),
            "horizon_json": json.dumps(asdict(self.horizon)),
            "justification_json": json.dumps(asdict(self.justification)),
            "guidance_json": json.dumps(asdict(self.guidance)),
            "ai_provider": self.ai_provider,
            "ai_model": self.ai_model,
        }
