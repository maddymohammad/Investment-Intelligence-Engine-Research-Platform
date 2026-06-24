from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── AI provider ──────────────────────────────────────────────
    ai_provider: str = "claude"  # claude | openai

    # Claude
    anthropic_api_key: Optional[str] = None
    claude_analysis_model: str = "claude-opus-4-8"
    claude_screening_model: str = "claude-haiku-4-5-20251001"

    # OpenAI
    openai_api_key: Optional[str] = None
    openai_analysis_model: str = "gpt-4o"
    openai_screening_model: str = "gpt-4o-mini"

    # ─── Data APIs ────────────────────────────────────────────────
    alpha_vantage_api_key: Optional[str] = None
    fmp_api_key: Optional[str] = None
    news_api_key: Optional[str] = None
    fred_api_key: Optional[str] = None

    # ─── Email ────────────────────────────────────────────────────
    email_sender: Optional[str] = None
    email_app_password: Optional[str] = None
    email_recipient: Optional[str] = None
    sendgrid_api_key: Optional[str] = None

    # ─── GitHub ───────────────────────────────────────────────────
    github_token: Optional[str] = None
    github_repo: Optional[str] = None
    github_branch: str = "main"

    # ─── Database ─────────────────────────────────────────────────
    database_url: str = "sqlite:///db/investment.db"

    # ─── Market ───────────────────────────────────────────────────
    run_timezone: str = "Asia/Kolkata"
    small_cap_max_market_cap_cr: float = 5000.0    # < 5 000 Cr INR → small cap
    large_cap_min_market_cap_cr: float = 20000.0   # > 20 000 Cr INR → large cap
    stock_universe_size: int = 500

    # ─── Recommendations ──────────────────────────────────────────
    confidence_threshold: float = 0.65   # stocks below this are dropped
    max_small_cap_picks: int = 2
    max_large_cap_picks: int = 2

    # ─── Paper portfolio ──────────────────────────────────────────
    paper_portfolio_initial_capital: float = 1_000_000.0   # 10 lakh INR
    paper_portfolio_max_position_pct: float = 0.25          # 25 % max per pick

    # ─── Application ──────────────────────────────────────────────
    reports_dir: str = "reports/daily"
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
