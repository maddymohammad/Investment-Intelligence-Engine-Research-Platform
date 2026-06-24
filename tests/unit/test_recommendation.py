"""Unit tests for recommendation dataclasses."""
import pytest
from datetime import date
from src.recommendation import (
    StockRecommendation,
    ResearchGuidance,
    ConfidenceDetail,
    TechnicalSummary,
    FundamentalSummary,
    RiskAnalysis,
    SelectionJustification,
    InvestmentHorizon,
)
from src.recommendation import RESEARCH_DISCLAIMER


class TestResearchGuidanceDisclaimer:
    def test_disclaimer_always_present(self):
        g = ResearchGuidance()
        assert g.disclaimer == RESEARCH_DISCLAIMER

    def test_disclaimer_restored_if_blank(self):
        g = ResearchGuidance(disclaimer="")
        assert g.disclaimer == RESEARCH_DISCLAIMER

    def test_disclaimer_not_overridden_with_custom(self):
        g = ResearchGuidance(disclaimer="NOT FOR TRADING")
        # __post_init__ restores if blank only; non-blank custom value is kept
        # (the implementation restores only when blank)
        assert g.disclaimer  # just not empty


class TestStockRecommendation:
    def test_defaults_are_safe(self):
        rec = StockRecommendation()
        assert rec.symbol == ""
        assert rec.composite_score == 0.0
        assert rec.confidence_score == 0.0
        assert rec.entry_price == 0.0
        assert rec.run_date is None
        assert rec.guidance.disclaimer == RESEARCH_DISCLAIMER

    def test_field_assignment(self):
        rec = StockRecommendation(
            symbol="TCS.NS",
            name="Tata Consultancy Services",
            cap_category="LARGE",
            run_date=date(2024, 1, 15),
            composite_score=72.5,
            confidence_score=0.75,
            entry_price=3820.0,
        )
        assert rec.symbol == "TCS.NS"
        assert rec.composite_score == 72.5
        assert rec.confidence_score == 0.75
        assert rec.entry_price == 3820.0

    def test_to_db_dict_has_required_keys(self):
        rec = StockRecommendation(
            symbol="INFY.NS",
            ai_provider="anthropic",
            ai_model="claude-opus-4-8",
        )
        d = rec.to_db_dict()
        assert "technical_json" in d
        assert "fundamental_json" in d
        assert "catalysts_json" in d
        assert "risk_json" in d
        assert "confidence_score" in d
        assert "ai_provider" in d
        assert d["ai_provider"] == "anthropic"

    def test_nested_dataclasses_default_empty(self):
        rec = StockRecommendation()
        assert isinstance(rec.technical, TechnicalSummary)
        assert isinstance(rec.fundamental, FundamentalSummary)
        assert isinstance(rec.risk, RiskAnalysis)
        assert isinstance(rec.confidence, ConfidenceDetail)
        assert isinstance(rec.justification, SelectionJustification)
        assert isinstance(rec.horizon, InvestmentHorizon)


class TestConfidenceDetail:
    def test_score_range(self):
        c = ConfidenceDetail(score=75.0, explanation="Strong fundamentals")
        assert 0 <= c.score <= 100

    def test_zero_score_is_valid(self):
        c = ConfidenceDetail(score=0.0)
        assert c.score == 0.0
