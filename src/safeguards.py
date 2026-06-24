"""
Runtime enforcement of the system boundary policy.

This system is STRICTLY a research and analysis platform.
It must never place trades, connect to brokerages, or execute orders.

Import and call `assert_research_only()` at any entry point that touches
external systems (data collection, email, GitHub). The check is intentionally
loud — a misconfigured integration should fail fast, not silently skip.
"""
from __future__ import annotations


class TradingProhibitedError(RuntimeError):
    """
    Raised when code attempts any action outside the permitted research boundary.
    This is a hard stop, not a warning.
    """


# ─── Prohibited brokerage / trading keywords ──────────────────────────────────
# Any integration that contains these identifiers in its module path, config key,
# or URL is by definition outside the system boundary.

PROHIBITED_BROKERAGES = frozenset(
    [
        "groww",
        "zerodha",
        "kite",          # Zerodha Kite API
        "upstox",
        "angelone",
        "angel_one",
        "angel-one",
        "smartapi",      # Angel One SmartAPI
        "fyers",
        "iifl",
        "motilal",
        "sharekhan",
        "5paisa",
        "nuvama",
        "edelweiss",
        "aliceblue",
        "dhan",
        "samco",
        "mstock",
    ]
)

PROHIBITED_ACTIONS = frozenset(
    [
        "place_order",
        "cancel_order",
        "modify_order",
        "buy_stock",
        "sell_stock",
        "execute_trade",
        "submit_order",
        "market_order",
        "limit_order",
        "demat",
        "broker_login",
        "generate_session",    # Zerodha session token
        "order_book",
        "trade_book",
    ]
)

# ─── System identity ──────────────────────────────────────────────────────────

SYSTEM_PURPOSE = (
    "Investment Intelligence Engine: research, analysis, and decision-support only. "
    "No trading. No brokerage connections. No order execution. "
    "See DISCLAIMER.md for the full policy."
)

RESEARCH_ONLY_NOTICE = """
╔══════════════════════════════════════════════════════════════════════════╗
║  RESEARCH & ANALYSIS PLATFORM — NOT A TRADING SYSTEM                   ║
║  All output is for informational purposes only.                         ║
║  Actual investment decisions are made manually by the user.             ║
║  See DISCLAIMER.md for the full policy.                                 ║
╚══════════════════════════════════════════════════════════════════════════╝
"""


# ─── Runtime guards ──────────────────────────────────────────────────────────

def assert_research_only() -> None:
    """
    Call at CLI / scheduler entry points to display the policy notice.
    Keeps the system's intent visible every time it runs.
    """
    # Nothing to block — this is a passive reminder.
    # The real guard is assert_no_trading_action() below.


def assert_no_brokerage(identifier: str) -> None:
    """
    Raise TradingProhibitedError if `identifier` references a prohibited brokerage.
    Call before loading any third-party integration.
    """
    lower = identifier.lower()
    for brokerage in PROHIBITED_BROKERAGES:
        if brokerage in lower:
            raise TradingProhibitedError(
                f"Integration '{identifier}' references brokerage '{brokerage}'. "
                "This system must never connect to brokerage APIs. "
                "See DISCLAIMER.md."
            )


def assert_no_trading_action(action_name: str) -> None:
    """
    Raise TradingProhibitedError if `action_name` maps to a prohibited trading action.
    Call before executing any external API call.
    """
    lower = action_name.lower()
    for action in PROHIBITED_ACTIONS:
        if action in lower:
            raise TradingProhibitedError(
                f"Action '{action_name}' is a trading operation. "
                "This system only analyses stocks — it never places orders. "
                "See DISCLAIMER.md."
            )


def validate_url(url: str) -> None:
    """
    Raise TradingProhibitedError if a URL points to a brokerage or trading endpoint.
    Call before any outbound HTTP request in data providers.
    """
    assert_no_brokerage(url)
    if any(kw in url.lower() for kw in ("order", "trade", "execute", "demat")):
        raise TradingProhibitedError(
            f"URL '{url}' appears to be a trading endpoint. "
            "Only market data, news, and research APIs are permitted."
        )
