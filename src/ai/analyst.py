"""
AI Analyst — fills the narrative sections of a StockRecommendation via LLM.

The pre-AI builder (src/recommendation/builder.py) populates all quantitative
fields. This module sends those numbers to the configured AI provider and
parses the structured JSON response back into the recommendation dataclasses.

Design:
  - One prompt per stock (full context in single call, minimises round-trips)
  - JSON response; non-critical parse failures degrade gracefully to safe defaults
  - Research-only language enforced in system prompt and post-processing
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from src.recommendation import (
    RESEARCH_DISCLAIMER,
    StockRecommendation,
)

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a senior equity research analyst specialising in Indian markets (NSE/BSE). "
    "You write institutional-quality research: data-driven, precise, and nuanced. "
    "Rules: "
    "(1) Base every claim on the quantitative data provided — never fabricate numbers. "
    "(2) If data is missing or null, acknowledge the gap explicitly. "
    "(3) This is RESEARCH ONLY — use words like 'monitor', 'watchlist', 'observe'; "
    "NEVER 'buy', 'sell', 'invest', 'place order', 'trade', or any directive action verb. "
    "(4) Return ONLY a valid JSON object — no markdown fences, no preamble, no trailing text. "
    "(5) All list fields must be arrays of strings (never null; use [] if empty). "
    "(6) Each narrative field: under 150 words. Lists: 2–4 items each."
)


def analyse_stock(rec: StockRecommendation, fund_data: dict) -> StockRecommendation:
    """
    Call the AI provider to fill all narrative fields in `rec`.
    Modifies rec in-place and returns it.
    """
    from src.ai.factory import get_ai_provider

    provider = get_ai_provider()
    prompt = _build_prompt(rec, fund_data)

    try:
        resp = provider.complete_analysis(
            prompt,
            system=_SYSTEM,
            max_tokens=3200,
            temperature=0.2,
        )
        parsed = _parse(resp.content, rec.symbol)
        if parsed:
            _apply(rec, parsed)
        else:
            _apply_fallback(rec)

        rec.ai_provider = provider.name
        rec.ai_model = resp.model
        rec.generated_at = datetime.utcnow()
        logger.info(
            "%s — AI analysis complete (%d tokens, model=%s)",
            rec.symbol, resp.total_tokens, resp.model,
        )
    except Exception as e:
        logger.error("%s — AI analysis failed: %s", rec.symbol, e)
        _apply_fallback(rec)

    return rec


# ─── Prompt ──────────────────────────────────────────────────────────────────

def _build_prompt(rec: StockRecommendation, fund_data: dict) -> str:
    t = rec.technical
    f = rec.fundamental
    r = rec.risk
    macro_ctx = ", ".join(rec.catalysts.macro_factors[:5]) or "No recent headlines"
    price_str = f"₹{rec.entry_price:,.0f}" if rec.entry_price else "N/A"

    return f"""Analyse {rec.symbol} ({rec.name}) — {rec.cap_category} CAP as of {rec.run_date}.

=== COMPOSITE SCORES (0–100) ===
Composite: {rec.composite_score:.1f} | Fundamental: {rec.fundamental_score:.1f} | Technical: {rec.technical_score:.1f}
Valuation: {rec.valuation_score:.1f}  | Risk: {rec.risk_score:.1f}

=== TECHNICAL DATA ===
RSI: {t.rsi or 'N/A'} ({t.rsi_interpretation})
MACD: {t.macd_status}
SMA-20: {t.sma_20 or 'N/A'} | SMA-50: {t.sma_50 or 'N/A'} | SMA-200: {t.sma_200 or 'N/A'}
Volume ratio (5d/20d): {t.volume_ratio_5d_vs_20d or 'N/A'} | ADX: {t.adx or 'N/A'}
Overall signal: {t.overall_technical_signal}
Current price: {price_str}

=== FUNDAMENTAL DATA ===
Sector: {f.sector or 'N/A'}
Revenue growth: {f.revenue_growth_pct or 'N/A'}% | EPS growth: {f.eps_growth_pct or 'N/A'}%
ROE: {f.roe_pct or 'N/A'}% | ROCE: {f.roce_pct or 'N/A'}%
D/E: {f.debt_to_equity or 'N/A'} | Profit margin: {f.profit_margin_pct or 'N/A'}% | Op. margin: {f.operating_margin_pct or 'N/A'}%
P/E: {f.pe_ratio or 'N/A'} | PEG: {f.peg_ratio or 'N/A'} | P/B: {f.pb_ratio or 'N/A'}
FCF: {f.free_cashflow or 'N/A'} | Sector rel. strength: {f.sector_relative_strength_pct or 'N/A'}%

=== RISK DATA ===
Beta: {r.beta or 'N/A'} | Annual volatility: {r.volatility_annual_pct or 'N/A'}% | Max drawdown: {r.max_drawdown_pct or 'N/A'}%

=== RECENT MARKET HEADLINES ===
{macro_ctx}

=== RESPONSE FORMAT ===
Return exactly this JSON (no markdown fences, no extra keys):
{{
  "technical": {{
    "macd_trend": "<2–3 sentences on MACD trend and momentum>",
    "ma_analysis": "<2–3 sentences on price vs SMAs>",
    "volume_trend": "<1–2 sentences on volume context>",
    "overall_technical_signal": "<STRONG_BUY_SIGNAL|BUY_SIGNAL|NEUTRAL|SELL_SIGNAL|STRONG_SELL_SIGNAL>"
  }},
  "fundamental": {{
    "revenue_growth_interpretation": "<1–2 sentences>",
    "eps_growth_interpretation": "<1–2 sentences>",
    "roe_interpretation": "<1–2 sentences>",
    "roce_interpretation": "<1–2 sentences>",
    "debt_assessment": "<1–2 sentences on leverage>",
    "margin_assessment": "<1–2 sentences on margins>",
    "valuation_assessment": "<2–3 sentences on P/E, PEG, P/B vs sector>",
    "sector_comparison": "<2–3 sentences comparing to sector peers>"
  }},
  "catalysts": {{
    "positive_developments": ["<item>", "<item>", "<item>"],
    "negative_developments": ["<item>", "<item>"],
    "upcoming_earnings": "<e.g. Q4 FY25 results expected May 2025, or null>",
    "major_events": ["<item>"],
    "sector_catalysts": ["<item>", "<item>"]
  }},
  "risk": {{
    "bear_case": "<3–4 sentences on downside scenario>",
    "sector_risks": ["<item>", "<item>"],
    "company_risks": ["<item>", "<item>"],
    "valuation_risks": ["<item>"],
    "technical_risks": ["<item>"],
    "volatility_assessment": "<1–2 sentences on beta and volatility>"
  }},
  "confidence": {{
    "explanation": "<2–3 sentences explaining the confidence score>",
    "key_positives": ["<item>", "<item>", "<item>"],
    "key_negatives": ["<item>", "<item>", "<item>"]
  }},
  "horizon": {{
    "short_term": "<1–4 week outlook in 2 sentences>",
    "medium_term": "<1–6 month outlook in 2 sentences>",
    "long_term": "<6–24 month thesis in 2–3 sentences>"
  }},
  "justification": {{
    "why_selected": "<2–3 sentences on why this stock vs. alternatives>",
    "bull_reasons": ["<item>", "<item>", "<item>"],
    "bear_reasons": ["<item>", "<item>", "<item>"],
    "key_assumptions": ["<item>", "<item>"]
  }},
  "guidance": {{
    "watchlist_entry_zone": "<e.g. ₹1,400–₹1,450 (monitoring reference only)>",
    "monitoring_levels": ["<support level>", "<resistance level>"],
    "profit_taking_zones": ["<zone 1>", "<zone 2>"],
    "stop_loss_zone": "<e.g. below ₹1,300 (research reference only)>"
  }}
}}"""


# ─── Parse + apply ────────────────────────────────────────────────────────────

def _parse(content: str, symbol: str) -> dict | None:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        end = -1 if lines[-1].strip() == "```" else len(lines)
        content = "\n".join(lines[1:end])
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("%s — JSON parse failed: %s", symbol, e)
        return None


def _apply(rec: StockRecommendation, d: dict) -> None:
    tech = d.get("technical", {})
    rec.technical.macd_trend = tech.get("macd_trend", "")
    rec.technical.ma_analysis = tech.get("ma_analysis", "")
    rec.technical.volume_trend = tech.get("volume_trend", "")
    if sig := tech.get("overall_technical_signal"):
        rec.technical.overall_technical_signal = sig

    fund = d.get("fundamental", {})
    rec.fundamental.revenue_growth_interpretation = fund.get("revenue_growth_interpretation", "")
    rec.fundamental.eps_growth_interpretation = fund.get("eps_growth_interpretation", "")
    rec.fundamental.roe_interpretation = fund.get("roe_interpretation", "")
    rec.fundamental.roce_interpretation = fund.get("roce_interpretation", "")
    rec.fundamental.debt_assessment = fund.get("debt_assessment", "")
    rec.fundamental.margin_assessment = fund.get("margin_assessment", "")
    rec.fundamental.valuation_assessment = fund.get("valuation_assessment", "")
    rec.fundamental.sector_comparison = fund.get("sector_comparison", "")

    cats = d.get("catalysts", {})
    rec.catalysts.positive_developments = _lst(cats.get("positive_developments"))
    rec.catalysts.negative_developments = _lst(cats.get("negative_developments"))
    rec.catalysts.upcoming_earnings = cats.get("upcoming_earnings") or None
    rec.catalysts.major_events = _lst(cats.get("major_events"))
    rec.catalysts.sector_catalysts = _lst(cats.get("sector_catalysts"))

    risk = d.get("risk", {})
    rec.risk.bear_case = risk.get("bear_case", "")
    rec.risk.sector_risks = _lst(risk.get("sector_risks"))
    rec.risk.company_risks = _lst(risk.get("company_risks"))
    rec.risk.valuation_risks = _lst(risk.get("valuation_risks"))
    rec.risk.technical_risks = _lst(risk.get("technical_risks"))
    rec.risk.volatility_assessment = risk.get("volatility_assessment", "")

    conf = d.get("confidence", {})
    rec.confidence.explanation = conf.get("explanation", "")
    rec.confidence.key_positives = _lst(conf.get("key_positives"))
    rec.confidence.key_negatives = _lst(conf.get("key_negatives"))

    hor = d.get("horizon", {})
    rec.horizon.short_term = hor.get("short_term", "")
    rec.horizon.medium_term = hor.get("medium_term", "")
    rec.horizon.long_term = hor.get("long_term", "")

    just = d.get("justification", {})
    rec.justification.why_selected = just.get("why_selected", "")
    rec.justification.bull_reasons = _lst(just.get("bull_reasons"))
    rec.justification.bear_reasons = _lst(just.get("bear_reasons"))
    rec.justification.key_assumptions = _lst(just.get("key_assumptions"))

    guid = d.get("guidance", {})
    rec.guidance.watchlist_entry_zone = guid.get("watchlist_entry_zone", "")
    rec.guidance.monitoring_levels = _lst(guid.get("monitoring_levels"))
    rec.guidance.profit_taking_zones = _lst(guid.get("profit_taking_zones"))
    rec.guidance.stop_loss_zone = guid.get("stop_loss_zone", "")
    rec.guidance.disclaimer = RESEARCH_DISCLAIMER  # always enforce canonical text


def _apply_fallback(rec: StockRecommendation) -> None:
    rec.confidence.explanation = (
        f"Composite score {rec.composite_score:.1f}/100 based on quantitative factors. "
        "AI narrative generation unavailable — refer to raw scores."
    )
    rec.confidence.key_positives = ["Review quantitative scores for full assessment"]
    rec.confidence.key_negatives = ["AI narrative unavailable — verify data manually"]
    rec.horizon.short_term = "Refer to RSI and MACD readings above."
    rec.horizon.medium_term = "Refer to fundamental scores and sector context."
    rec.horizon.long_term = "Refer to composite score and conduct qualitative research."
    rec.justification.why_selected = (
        f"Score {rec.composite_score:.1f}/100 exceeded the confidence threshold."
    )
    p = f"₹{rec.entry_price:,.0f}" if rec.entry_price else "current price"
    rec.guidance.watchlist_entry_zone = f"Near {p} (monitoring reference)"
    rec.guidance.disclaimer = RESEARCH_DISCLAIMER
    rec.ai_provider = "fallback"
    rec.ai_model = "none"
    rec.generated_at = datetime.utcnow()


def _lst(val) -> list:
    if isinstance(val, list):
        return [str(v) for v in val if v]
    return []
