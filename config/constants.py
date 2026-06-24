"""
Static reference data: NIFTY 50 tickers, sector map, market hours.
The bootstrap script fetches the full NIFTY 500 dynamically; this file
is the hardcoded fallback used when NSE India is unreachable.
"""

# ─── NIFTY 50 symbols (Yahoo Finance format: NSE suffix .NS) ─────
NIFTY50_SYMBOLS: list[str] = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS",
    "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BAJFINANCE.NS",
    "BHARTIARTL.NS", "BPCL.NS", "BRITANNIA.NS", "CIPLA.NS",
    "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS",
    "INDUSINDBK.NS", "INFY.NS", "ITC.NS", "JSWSTEEL.NS",
    "KOTAKBANK.NS", "LT.NS", "LTIM.NS", "M&M.NS",
    "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS",
    "SBIN.NS", "SUNPHARMA.NS", "TATACONSUM.NS", "TATAMOTORS.NS",
    "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TITAN.NS",
    "ULTRACEMCO.NS", "WIPRO.NS",
]

# NIFTY 50 index ticker on Yahoo Finance
NIFTY50_INDEX = "^NSEI"
SENSEX_INDEX = "^BSESN"
INDIA_VIX = "^INDIAVIX"

# ─── Benchmark start dates for paper-portfolio inception returns ──
BENCHMARK_INCEPTION_DATE = "2020-01-01"   # updated once portfolio starts

# ─── Market hours (IST, 24-h) ────────────────────────────────────
MARKET_OPEN_IST = "09:15"
MARKET_CLOSE_IST = "15:30"
DAILY_RUN_IST = "18:00"

# ─── Market cap thresholds (SEBI / NSE classification, Cr INR) ───
SMALL_CAP_MAX_CR = 5_000
MID_CAP_MAX_CR = 20_000
# > MID_CAP_MAX_CR → large cap

# ─── NSE India CSV URLs (primary universe source) ────────────────
NSE_NIFTY500_CSV_URL = (
    "https://niftyindices.com/IndexConstituent/ind_nifty500list.csv"
)
NSE_NIFTY50_CSV_URL = (
    "https://niftyindices.com/IndexConstituent/ind_nifty50list.csv"
)

# ─── Sector mapping (GICS-style, used when yfinance sector is None) ─
SYMBOL_TO_SECTOR: dict[str, str] = {
    "RELIANCE.NS": "Energy",
    "TCS.NS": "Information Technology",
    "HDFCBANK.NS": "Financials",
    "INFY.NS": "Information Technology",
    "ICICIBANK.NS": "Financials",
    "HINDUNILVR.NS": "Consumer Staples",
    "ITC.NS": "Consumer Staples",
    "SBIN.NS": "Financials",
    "BHARTIARTL.NS": "Communication Services",
    "BAJFINANCE.NS": "Financials",
}

# ─── NSE trading holidays 2025 (dd-mmm-yyyy) ─────────────────────
NSE_HOLIDAYS_2025: list[str] = [
    "2025-01-26",  # Republic Day
    "2025-03-14",  # Holi (tentative)
    "2025-04-14",  # Dr. Ambedkar Jayanti / Good Friday (overlap)
    "2025-04-18",  # Good Friday
    "2025-05-01",  # Maharashtra Day
    "2025-08-15",  # Independence Day
    "2025-10-02",  # Gandhi Jayanti
    "2025-10-21",  # Diwali Laxmi Pujan (tentative)
    "2025-10-22",  # Diwali Balipratipada (tentative)
    "2025-11-05",  # Guru Nanak Jayanti (tentative)
    "2025-12-25",  # Christmas
]

# ─── Scoring weights (sum = 1.0) ─────────────────────────────────
SCORE_WEIGHTS = {
    "fundamental": 0.40,
    "technical": 0.30,
    "sentiment": 0.20,
    "macro": 0.10,
}

# ─── Default position horizon ────────────────────────────────────
DEFAULT_POSITION_HORIZON_DAYS = 30
