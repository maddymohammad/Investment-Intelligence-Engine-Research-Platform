"""
Report generator: renders StockRecommendation objects to markdown and HTML.

The markdown file is the canonical output:
  - Self-contained (no external images)
  - Committed to GitHub
  - Readable in any markdown viewer
  - Source for HTML email body

HTML is rendered from markdown for email delivery.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ReportGenerator:

    def __init__(self, settings) -> None:
        self.settings = settings
        self.reports_dir = Path(settings.reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._template_dir = Path(__file__).parent.parent.parent / "templates"

    def generate(
        self,
        recommendations: list,
        run_date: date,
        market_ctx: dict,
    ) -> str:
        """
        Render and save the daily report.
        Returns path to the markdown file.
        """
        md_content = self._render_markdown(recommendations, run_date, market_ctx)

        md_path = self.reports_dir / f"{run_date}.md"
        md_path.write_text(md_content, encoding="utf-8")
        logger.info("Markdown report saved: %s", md_path)

        try:
            html = self._md_to_html(md_content, run_date)
            html_path = self.reports_dir / f"{run_date}.html"
            html_path.write_text(html, encoding="utf-8")
            logger.info("HTML report saved: %s", html_path)
        except Exception as e:
            logger.warning("HTML conversion skipped: %s", e)

        return str(md_path)

    # ─── Rendering ────────────────────────────────────────────────────────────

    def _render_markdown(
        self, recommendations: list, run_date: date, market_ctx: dict
    ) -> str:
        try:
            from jinja2 import Environment, FileSystemLoader

            env = Environment(
                loader=FileSystemLoader(str(self._template_dir)),
                autoescape=False,
                trim_blocks=True,
                lstrip_blocks=True,
            )

            def n(v, decimals: int = 0, suffix: str = "") -> str:
                """Format number with comma separators; return '—' for None."""
                if v is None:
                    return "—"
                try:
                    formatted = f"{float(v):,.{decimals}f}"
                    return f"{formatted}{suffix}"
                except (TypeError, ValueError):
                    return str(v)

            def sign(v, decimals: int = 2) -> str:
                if v is None:
                    return "—"
                try:
                    val = float(v)
                    return f"{val:+,.{decimals}f}"
                except (TypeError, ValueError):
                    return str(v)

            env.filters["n"] = n
            env.filters["sign"] = sign

            template = env.get_template("report.md.j2")
            return template.render(
                recommendations=recommendations,
                run_date=run_date,
                market=market_ctx,
            )
        except Exception as e:
            logger.error("Jinja2 render failed (%s), using fallback", e)
            return self._fallback_markdown(recommendations, run_date, market_ctx)

    def _fallback_markdown(
        self, recommendations: list, run_date: date, market_ctx: dict
    ) -> str:
        from src.recommendation import RESEARCH_DISCLAIMER

        lines = [
            f"# Investment Intelligence Report — {run_date}",
            "",
            f"> {RESEARCH_DISCLAIMER}",
            "",
            "## Market Context",
        ]
        if market_ctx.get("nifty50_close"):
            chg = market_ctx.get("nifty50_change_pct") or 0.0
            lines.append(
                f"- **NIFTY 50:** {market_ctx['nifty50_close']:,.0f} ({chg:+.2f}%)"
            )
        if market_ctx.get("sensex_close"):
            chg = market_ctx.get("sensex_change_pct") or 0.0
            lines.append(
                f"- **SENSEX:** {market_ctx['sensex_close']:,.0f} ({chg:+.2f}%)"
            )
        if not recommendations:
            lines += ["", "## No Recommendations Today", ""]
            return "\n".join(lines)

        lines += ["", "## Picks"]
        for rec in recommendations:
            lines += [
                "",
                f"---",
                f"### {rec.symbol} — {rec.name} ({rec.cap_category})",
                f"**Score:** {rec.composite_score:.1f}/100 | "
                f"**Price:** ₹{rec.entry_price:,.0f} | "
                f"**Confidence:** {rec.confidence.score:.0f}/100",
                "",
                f"**Technical:** RSI {rec.technical.rsi or '—'} | MACD {rec.technical.macd_status}",
                f"{rec.technical.ma_analysis}",
                "",
                f"**Fundamental:** ROE {rec.fundamental.roe_pct or '—'}% | "
                f"ROCE {rec.fundamental.roce_pct or '—'}% | "
                f"D/E {rec.fundamental.debt_to_equity or '—'}",
                f"{rec.fundamental.valuation_assessment}",
                "",
                f"**Horizons:**",
                f"- Short-term: {rec.horizon.short_term}",
                f"- Medium-term: {rec.horizon.medium_term}",
                f"- Long-term: {rec.horizon.long_term}",
                "",
                f"**Risk:** {rec.risk.bear_case}",
                "",
                f"> {rec.guidance.disclaimer}",
            ]

        return "\n".join(lines)

    def _md_to_html(self, md_content: str, run_date: date) -> str:
        import markdown2
        body = markdown2.markdown(
            md_content,
            extras=["tables", "fenced-code-blocks", "header-ids", "break-on-newline"],
        )
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Investment Intelligence Report — {run_date}</title>
<style>
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    max-width: 960px; margin: 0 auto; padding: 2rem;
    color: #1a1a2e; background: #f8f9fa; line-height: 1.6;
  }}
  h1 {{ color: #16213e; border-bottom: 3px solid #0f3460; padding-bottom: .5rem; }}
  h2 {{ color: #0f3460; border-left: 4px solid #e94560; padding-left: .75rem; margin-top: 2rem; }}
  h3 {{ color: #16213e; }}
  h4 {{ color: #0f3460; }}
  blockquote {{
    background: #fff3cd; border-left: 4px solid #ffc107;
    padding: .75rem 1rem; margin: 1rem 0; border-radius: 4px;
    font-size: .9rem;
  }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th {{ background: #16213e; color: white; padding: .5rem .75rem; text-align: left; font-size: .85rem; }}
  td {{ padding: .5rem .75rem; border-bottom: 1px solid #dee2e6; font-size: .9rem; }}
  tr:nth-child(even) {{ background: #f1f3f5; }}
  code {{ background: #e9ecef; padding: .1rem .3rem; border-radius: 3px; font-size: .85rem; }}
  hr {{ border: 0; border-top: 2px solid #dee2e6; margin: 2rem 0; }}
  ul {{ padding-left: 1.5rem; }}
  li {{ margin: .3rem 0; }}
</style>
</head>
<body>
{body}
</body>
</html>"""
