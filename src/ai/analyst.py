"""
AI Analyst — fills the narrative sections of a StockRecommendation.

TWO MODES (selected automatically):

  1. AI mode (when ANTHROPIC_API_KEY or OPENAI_API_KEY is set):
     Sends the quantitative data to the configured LLM provider and parses
     the structured JSON response back into the recommendation dataclasses.

  2. FREE quant mode (when no API key is configured — the default):
     Generates all narrative sections deterministically from the
     quantitative data the pipeline has already computed (RSI, MACD,
     SMAs, ROE, P/E, volatility, sector strength…). Zero API calls,
     zero cost, fully offline. The pipeline NEVER fails because a
     key is missing.

Design:
  - One prompt per stock in AI mode (full context in single call)
  - Non-critical failures in AI mode degrade gracefully to quant mode
  - Research-only language enforced in both modes
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
    Fill all narrative fields in `rec`.
    Uses the AI provider when a key is configured; otherwise uses the
    free deterministic quant-narrative engine. Never raises on missing keys.
    Modifies rec in-place and returns it.
    """
    from src.ai.factory import get_ai_provider, is_ai_configured

    # ── FREE MODE — no key configured ─────────────────────────────────────
    if not is_ai_configured():
        logger.info(
            "%s — no AI API key configured; using free rule-based narratives",
            rec.symbol,
        )
        _apply_quant_narrative(rec, fund_data)
        return rec

    # ── AI MODE ───────────────────────────────────────────────────────────
    prompt = _build_prompt(rec, fund_data)

    try:
        provider = get_ai_provider()
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
            _apply_quant_narrative(rec, fund_data)

        rec.ai_provider = provider.name
        rec.ai_model = resp.model
        rec.generated_at = datetime.utcnow()
        logger.info(
            "%s — AI analysis complete (%d tokens, model=%s)",
            rec.symbol, resp.total_tokens, resp.model,
        )
    except Exception as e:
        logger.error("%s — AI analysis failed: %s — falling back to quant mode", rec.symbol, e)
        _apply_quant_narrative(rec, fund_data)

    return rec


# ─── Prompt (AI mode) ─────────────────────────────────────────────────────────

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


# ─── Parse + apply (AI mode) ──────────────────────────────────────────────────

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


# ══════════════════════════════════════════════════════════════════════════════
# FREE QUANT MODE — deterministic narratives from quantitative data
# ══════════════════════════════════════════════════════════════════════════════

def _fmt(v, unit: str = "", nd: int = 1) -> str:
    """None-safe number formatter."""
    if v is None:
        return "N/A"
    try:
        return f"{float(v):,.{nd}f}{unit}"
    except (TypeError, ValueError):
        return "N/A"


def _rupees(v) -> str:
    if not v:
        return "current price"
    return f"₹{float(v):,.0f}"


def _apply_quant_narrative(rec: StockRecommendation, fund_data: dict | None = None) -> None:
    """
    Fill every narrative field from the quantitative data already computed
    by the analysis engine. Deterministic, offline, free.
    """
    t = rec.technical
    f = rec.fundamental
    r = rec.risk
    fund_data = fund_data or {}

    # ── TECHNICAL narratives ──────────────────────────────────────────────
    macd = (t.macd_status or "NEUTRAL").upper()
    if "BULL" in macd:
        t.macd_trend = (
            "MACD is in a bullish configuration with the signal line crossed to the "
            "upside, indicating positive short-term momentum. Momentum studies favour "
            "continuation while this alignment holds."
        )
    elif "BEAR" in macd:
        t.macd_trend = (
            "MACD is in a bearish configuration with momentum tilted to the downside. "
            "A cross back above the signal line would be the first indication of a "
            "momentum shift worth monitoring."
        )
    else:
        t.macd_trend = (
            "MACD is broadly neutral with no decisive momentum signal. "
            "The next directional cross will be the more informative event to monitor."
        )

    price = rec.entry_price or 0.0
    above = [x for x in [("SMA-20", t.sma_20), ("SMA-50", t.sma_50), ("SMA-200", t.sma_200)]
             if x[1] and price and price > x[1]]
    below = [x for x in [("SMA-20", t.sma_20), ("SMA-50", t.sma_50), ("SMA-200", t.sma_200)]
             if x[1] and price and price <= x[1]]
    if price and len(above) == 3:
        t.ma_analysis = (
            f"Price ({_rupees(price)}) trades above all three key moving averages "
            f"(20/50/200-day), a classic uptrend structure. The rising SMA-200 at "
            f"{_fmt(t.sma_200, nd=0)} acts as the primary long-term trend reference."
        )
    elif price and len(below) == 3:
        t.ma_analysis = (
            f"Price ({_rupees(price)}) is below all three key moving averages, a "
            f"downtrend structure. The SMA-200 at {_fmt(t.sma_200, nd=0)} overhead is "
            f"the key level a recovery would need to reclaim."
        )
    elif price:
        above_names = ", ".join(a[0] for a in above) or "none"
        below_names = ", ".join(b[0] for b in below) or "none"
        t.ma_analysis = (
            f"Mixed moving-average structure: price is above {above_names} but below "
            f"{below_names}. Consolidation phases like this typically resolve in the "
            f"direction of the eventual SMA realignment."
        )
    else:
        t.ma_analysis = "Insufficient price data to assess moving-average structure."

    vr = t.volume_ratio_5d_vs_20d
    if vr and vr > 1.2:
        t.volume_trend = (
            f"Recent volume is elevated at {_fmt(vr, 'x')} the 20-day average, "
            "suggesting increased participation behind current price action."
        )
    elif vr and vr < 0.8:
        t.volume_trend = (
            f"Volume is subdued at {_fmt(vr, 'x')} the 20-day average — moves on "
            "light volume carry less conviction and merit confirmation."
        )
    elif vr:
        t.volume_trend = f"Volume is running in line with the 20-day average ({_fmt(vr, 'x')})."
    else:
        t.volume_trend = "Volume data unavailable for this period."

    # ── FUNDAMENTAL narratives ────────────────────────────────────────────
    def growth_text(val, label):
        if val is None:
            return f"{label} data is unavailable from the provider; treat this gap as an open research item."
        if val >= 15:
            return f"{label} of {_fmt(val, '%')} is strong, comfortably ahead of nominal GDP growth."
        if val >= 5:
            return f"{label} of {_fmt(val, '%')} is moderate and broadly in line with the wider market."
        if val >= 0:
            return f"{label} of {_fmt(val, '%')} is muted; watch coming quarters for reacceleration."
        return f"{label} is contracting at {_fmt(val, '%')} — a key item to monitor in upcoming results."

    f.revenue_growth_interpretation = growth_text(f.revenue_growth_pct, "Revenue growth")
    f.eps_growth_interpretation = growth_text(f.eps_growth_pct, "EPS growth")

    def quality_text(val, label):
        if val is None:
            return f"{label} data unavailable."
        if val >= 18:
            return f"{label} of {_fmt(val, '%')} indicates highly efficient capital deployment."
        if val >= 12:
            return f"{label} of {_fmt(val, '%')} is healthy and above typical cost of capital."
        return f"{label} of {_fmt(val, '%')} is modest; capital efficiency is a watch item."

    f.roe_interpretation = quality_text(f.roe_pct, "ROE")
    f.roce_interpretation = quality_text(f.roce_pct, "ROCE")

    de = f.debt_to_equity
    if de is None:
        f.debt_assessment = "Leverage data unavailable."
    elif de < 0.5:
        f.debt_assessment = f"Debt-to-equity of {_fmt(de, nd=2)} is conservative, leaving balance-sheet flexibility."
    elif de <= 1.0:
        f.debt_assessment = f"Debt-to-equity of {_fmt(de, nd=2)} is moderate and serviceable at current profitability."
    else:
        f.debt_assessment = f"Debt-to-equity of {_fmt(de, nd=2)} is elevated; interest-rate sensitivity is a live risk."

    pm = f.profit_margin_pct
    if pm is None:
        f.margin_assessment = "Margin data unavailable."
    elif pm >= 15:
        f.margin_assessment = (
            f"Net margin of {_fmt(pm, '%')} (operating: {_fmt(f.operating_margin_pct, '%')}) "
            "indicates solid pricing power."
        )
    elif pm >= 7:
        f.margin_assessment = (
            f"Net margin of {_fmt(pm, '%')} is adequate; operating margin of "
            f"{_fmt(f.operating_margin_pct, '%')} frames the efficiency picture."
        )
    else:
        f.margin_assessment = f"Thin net margin of {_fmt(pm, '%')} leaves limited buffer against cost inflation."

    pe, peg, pb, spe = f.pe_ratio, f.peg_ratio, f.pb_ratio, f.sector_avg_pe
    val_parts = []
    if pe is not None:
        if spe:
            rel = "a premium to" if pe > spe else "a discount to"
            val_parts.append(f"P/E of {_fmt(pe)} trades at {rel} the sector average of {_fmt(spe)}")
        else:
            val_parts.append(f"P/E of {_fmt(pe)}")
    if peg is not None:
        peg_read = "growth-adjusted value" if peg < 1 else ("fair growth pricing" if peg <= 2 else "rich growth pricing")
        val_parts.append(f"PEG of {_fmt(peg, nd=2)} suggests {peg_read}")
    if pb is not None:
        val_parts.append(f"P/B stands at {_fmt(pb, nd=2)}")
    f.valuation_assessment = (
        ("; ".join(val_parts) + ". Valuation should be read alongside the growth and quality metrics above.")
        if val_parts else "Valuation multiples unavailable from the data provider."
    )

    srs = f.sector_relative_strength_pct
    sector = f.sector or "its sector"
    if srs is not None:
        direction = "outperforming" if srs >= 0 else "underperforming"
        f.sector_comparison = (
            f"The stock is {direction} {sector} by {_fmt(abs(srs), '%')} over the "
            f"measurement window, which frames its relative momentum among peers."
        )
    else:
        f.sector_comparison = f"Sector-relative performance data for {sector} is unavailable."

    # ── CATALYSTS (data-derived; no news synthesis in free mode) ──────────
    pos, neg = [], []
    if f.revenue_growth_pct is not None and f.revenue_growth_pct >= 15:
        pos.append(f"Revenue growing {_fmt(f.revenue_growth_pct, '%')} YoY")
    if f.roe_pct is not None and f.roe_pct >= 18:
        pos.append(f"ROE of {_fmt(f.roe_pct, '%')} signals efficient capital use")
    if "BULL" in macd:
        pos.append("Positive MACD momentum configuration")
    if srs is not None and srs > 0:
        pos.append(f"Outperforming {sector} by {_fmt(srs, '%')}")
    if de is not None and de > 1.0:
        neg.append(f"Elevated leverage (D/E {_fmt(de, nd=2)})")
    if f.eps_growth_pct is not None and f.eps_growth_pct < 0:
        neg.append(f"EPS contracting ({_fmt(f.eps_growth_pct, '%')})")
    if pe is not None and spe and pe > spe * 1.3:
        neg.append("Valuation premium >30% versus sector average")
    if "BEAR" in macd:
        neg.append("Bearish MACD momentum")

    rec.catalysts.positive_developments = pos[:4] or ["Composite quantitative profile above selection threshold"]
    rec.catalysts.negative_developments = neg[:3] or ["No red flags in the quantitative dataset; qualitative review still advised"]
    rec.catalysts.upcoming_earnings = None  # not derivable without a data source
    rec.catalysts.major_events = []
    rec.catalysts.sector_catalysts = (
        [f"{sector} sector relative move of {_fmt(srs, '%')} over the window"] if srs is not None else []
    )

    # ── RISK narratives ───────────────────────────────────────────────────
    vol = r.volatility_annual_pct
    beta = r.beta
    mdd = r.max_drawdown_pct

    r.bear_case = (
        f"In a drawdown scenario, historical behaviour suggests meaningful downside: "
        f"annualised volatility of {_fmt(vol, '%')} and a maximum historical drawdown of "
        f"{_fmt(mdd, '%')} frame the realistic risk envelope. "
        f"{'A beta of ' + _fmt(beta, nd=2) + ' implies amplified moves versus the index. ' if beta and beta > 1.1 else ''}"
        "A break of long-term trend support combined with any fundamental deterioration "
        "(margin compression, growth slowdown) would define the bear path."
    )
    r.sector_risks = [
        f"Rotation away from the {sector} sector",
        f"Regulatory or policy changes affecting {sector}",
    ]
    company_risks = []
    if de is not None and de > 1.0:
        company_risks.append(f"Balance-sheet leverage (D/E {_fmt(de, nd=2)}) raises rate sensitivity")
    if f.revenue_growth_pct is not None and f.revenue_growth_pct < 5:
        company_risks.append("Sub-5% revenue growth limits operating leverage")
    if not company_risks:
        company_risks.append("Execution risk on maintaining current growth and margin profile")
    r.company_risks = company_risks
    r.valuation_risks = (
        [f"P/E of {_fmt(pe)} leaves limited room for earnings disappointment"]
        if pe is not None and (spe is None or pe > (spe or 0)) else
        ["Multiple de-rating if broad-market valuations compress"]
    )
    r.technical_risks = (
        [f"A close below SMA-200 ({_fmt(t.sma_200, nd=0)}) would invalidate the long-term trend structure"]
        if t.sma_200 else ["Trend structure unconfirmed — insufficient moving-average data"]
    )
    r.volatility_assessment = (
        f"Beta of {_fmt(beta, nd=2)} with annualised volatility of {_fmt(vol, '%')} "
        f"characterises the stock's risk profile relative to the index."
    )

    # ── CONFIDENCE ────────────────────────────────────────────────────────
    pillars = {
        "fundamental": rec.fundamental_score,
        "technical": rec.technical_score,
        "valuation": rec.valuation_score,
        "risk": rec.risk_score,
    }
    strongest = max(pillars, key=pillars.get)
    weakest = min(pillars, key=pillars.get)
    rec.confidence.explanation = (
        f"Composite score of {rec.composite_score:.1f}/100 generated by the deterministic "
        f"quantitative engine (rule-based free mode — no AI narrative model). The {strongest} "
        f"pillar is the strongest driver ({pillars[strongest]:.0f}); {weakest} is the weakest "
        f"({pillars[weakest]:.0f})."
    )
    rec.confidence.key_positives = (pos or ["Composite score above threshold"])[:3]
    rec.confidence.key_negatives = (neg or ["Narrative depth limited in free mode — verify qualitatively"])[:3]

    # ── HORIZON ───────────────────────────────────────────────────────────
    rsi = t.rsi
    rsi_txt = (
        f"RSI at {_fmt(rsi, nd=0)} " + (
            "is overbought — near-term consolidation is common from such readings."
            if rsi and rsi >= 70 else
            "is oversold — watch for stabilisation signals."
            if rsi and rsi <= 30 else
            "sits in the neutral band."
        )
    ) if rsi is not None else "RSI unavailable."
    rec.horizon.short_term = (
        f"1–4 weeks: technical signal reads {t.overall_technical_signal or 'NEUTRAL'}. {rsi_txt}"
    )
    rec.horizon.medium_term = (
        f"1–6 months: the fundamental score of {rec.fundamental_score:.0f}/100 and "
        f"{'positive' if (srs or 0) >= 0 else 'negative'} sector-relative momentum shape the medium-term picture."
    )
    rec.horizon.long_term = (
        f"6–24 months: sustainability depends on holding ROE near {_fmt(f.roe_pct, '%')} "
        f"and revenue growth near {_fmt(f.revenue_growth_pct, '%')}; the valuation reading above "
        "frames the multiple risk over this horizon."
    )

    # ── JUSTIFICATION ─────────────────────────────────────────────────────
    rec.justification.why_selected = (
        f"Composite score of {rec.composite_score:.1f}/100 cleared the selection threshold, "
        f"ranking it ahead of screened alternatives primarily on the {strongest} pillar."
    )
    rec.justification.bull_reasons = (pos or ["Quantitative profile above threshold"])[:3]
    rec.justification.bear_reasons = (neg or ["Standard market and execution risk"])[:3]
    rec.justification.key_assumptions = [
        "Provider-reported fundamentals (Yahoo Finance) are accurate and current",
        "No undisclosed corporate actions or material events pending",
    ]

    # ── GUIDANCE (informational levels from computed technicals) ──────────
    supports = t.support_levels or []
    resistances = t.resistance_levels or []
    if supports:
        lo = supports[0]
        rec.guidance.watchlist_entry_zone = (
            f"₹{lo:,.0f} – ₹{lo * 1.02:,.0f} (near computed support; monitoring reference only)"
        )
    elif price:
        rec.guidance.watchlist_entry_zone = (
            f"₹{price * 0.98:,.0f} – ₹{price * 1.02:,.0f} (around current price; monitoring reference only)"
        )
    else:
        rec.guidance.watchlist_entry_zone = "Insufficient data for a reference zone"

    rec.guidance.monitoring_levels = (
        [f"Support: ₹{s:,.0f}" for s in supports[:2]] +
        [f"Resistance: ₹{x:,.0f}" for x in resistances[:2]]
    ) or ["Key levels unavailable — insufficient price history"]
    rec.guidance.profit_taking_zones = (
        [f"₹{x:,.0f} zone (research reference only)" for x in resistances[:2]]
        or ["Not derivable without resistance data"]
    )
    if supports:
        rec.guidance.stop_loss_zone = f"Below ₹{min(supports):,.0f} (research reference only)"
    elif t.sma_200:
        rec.guidance.stop_loss_zone = f"Below SMA-200 at ₹{t.sma_200:,.0f} (research reference only)"
    else:
        rec.guidance.stop_loss_zone = "Not derivable — insufficient data"
    rec.guidance.disclaimer = RESEARCH_DISCLAIMER

    # ── Provenance ────────────────────────────────────────────────────────
    rec.ai_provider = "quant-rules"
    rec.ai_model = "deterministic-free-v1"
    rec.generated_at = datetime.utcnow()


# Backwards-compatible alias (older code/tests may import this name)
def _apply_fallback(rec: StockRecommendation) -> None:
    _apply_quant_narrative(rec, {})


def _lst(val) -> list:
    if isinstance(val, list):
        return [str(v) for v in val if v]
    return []
