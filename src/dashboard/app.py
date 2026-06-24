"""
Streamlit dashboard — Investment Intelligence Engine.

Run with:  streamlit run src/dashboard/app.py
Or via:    make dashboard

Pages:
  Overview    — today's AI research picks with full analysis
  History     — historical recommendation log with outcomes
  Portfolio   — paper portfolio performance vs NIFTY 50 benchmark
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import streamlit as st

# ─── Page config (must be first Streamlit call) ───────────────────────────────

st.set_page_config(
    page_title="Investment Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── DB bootstrap ─────────────────────────────────────────────────────────────

@st.cache_resource
def _init():
    from src.storage.db import init_db
    init_db()

_init()


# ─── Sidebar ──────────────────────────────────────────────────────────────────

st.sidebar.title("📊 Investment Intelligence")
st.sidebar.caption("Research & Analysis Platform")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    ["Overview", "History", "Portfolio"],
    label_visibility="collapsed",
)
st.sidebar.markdown("---")
st.sidebar.warning(
    "**RESEARCH ONLY** — Not investment advice. "
    "This system does not place trades or connect to any brokerage."
)


# ─── Data loaders ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_recommendations(limit: int = 60):
    from src.storage.db import get_session
    from src.storage.models import Recommendation
    with get_session() as session:
        rows = (
            session.query(Recommendation)
            .order_by(Recommendation.run_date.desc(), Recommendation.rank_position)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "run_date": r.run_date,
                "symbol": r.symbol,
                "cap_category": r.cap_category,
                "rank_position": r.rank_position,
                "entry_price": r.entry_price,
                "target_price": r.target_price,
                "stop_loss": r.stop_loss,
                "confidence_score": r.confidence_score,
                "time_horizon": r.time_horizon,
                "status": r.status,
                "exit_price": r.exit_price,
                "return_pct": r.return_pct,
                "closed_at": r.closed_at,
            }
            for r in rows
        ]


@st.cache_data(ttl=300)
def load_portfolio_snapshots():
    from src.storage.db import get_session
    from src.storage.models import PortfolioSnapshot
    with get_session() as session:
        rows = (
            session.query(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.snapshot_date)
            .all()
        )
        return [
            {
                "date": r.snapshot_date,
                "total": r.total_value_inr,
                "return_pct": r.total_return_pct,
                "nifty_return_pct": r.nifty50_return_pct,
                "alpha": r.alpha,
                "max_dd": r.max_drawdown_pct,
                "sharpe": r.sharpe_ratio,
                "win_rate": r.win_rate,
                "open": r.open_positions,
                "closed": r.total_trades,
                "cagr": r.cagr,
            }
            for r in rows
        ]


@st.cache_data(ttl=300)
def load_latest_run():
    from src.storage.db import get_session
    from src.storage.repository import RunLogRepository
    with get_session() as session:
        log = RunLogRepository().get_latest(session)
        if log:
            return {
                "run_date": log.run_date,
                "status": log.status,
                "screened": log.stocks_screened,
                "selected": log.stocks_selected,
                "error": log.error_message,
                "end_time": log.end_time,
            }
        return None


@st.cache_data(ttl=300)
def load_latest_report_path():
    from src.storage.db import get_session
    from src.storage.repository import RunLogRepository
    with get_session() as session:
        log = RunLogRepository().get_latest(session)
        if log and log.report_path:
            return log.report_path
    return None


# ─── PAGE: Overview ───────────────────────────────────────────────────────────

def page_overview():
    st.title("📋 Today's Research Overview")

    run_log = load_latest_run()
    if not run_log:
        st.warning("No runs recorded yet. Run `python main.py run` to execute the daily pipeline.")
        return

    # Run metadata
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Last Run", str(run_log["run_date"]))
    col2.metric(
        "Status",
        run_log["status"],
        delta=None,
        delta_color="off",
    )
    col3.metric("Stocks Screened", run_log["screened"] or "—")
    col4.metric("Stocks Selected", run_log["selected"] or "—")

    if run_log["error"]:
        st.error(f"Last run error: {run_log['error']}")

    st.divider()

    # Latest recommendations
    all_recs = load_recommendations(limit=10)
    if not all_recs:
        st.info("No recommendations in database yet.")
        return

    today_recs = [r for r in all_recs if r["run_date"] == run_log["run_date"]]

    if not today_recs:
        st.info(f"No recommendations for {run_log['run_date']}.")
        # Show last available date
        if all_recs:
            last_date = all_recs[0]["run_date"]
            st.caption(f"Showing latest available: {last_date}")
            today_recs = [r for r in all_recs if r["run_date"] == last_date]

    if not today_recs:
        st.warning("No picks met the confidence threshold today.")
        return

    # Summary cards
    st.subheader(f"Research Picks — {today_recs[0]['run_date']}")
    cols = st.columns(len(today_recs))
    for col, rec in zip(cols, today_recs):
        with col:
            st.markdown(f"### {rec['symbol']}")
            st.caption(f"{rec['cap_category']} CAP")
            st.metric(
                "Entry Price",
                f"₹{rec['entry_price']:,.0f}",
            )
            st.metric(
                "Confidence",
                f"{(rec['confidence_score'] or 0) * 100:.0f}%",
            )
            st.caption(f"Status: {rec['status']}")

    st.divider()

    # Markdown report viewer
    report_dir = Path("reports/daily")
    if today_recs:
        report_file = report_dir / f"{today_recs[0]['run_date']}.md"
        if report_file.exists():
            st.subheader("Full Research Report")
            with st.expander("View complete report", expanded=True):
                st.markdown(report_file.read_text(encoding="utf-8"))
        else:
            st.info("Report file not found. Run the daily pipeline to generate it.")


# ─── PAGE: History ────────────────────────────────────────────────────────────

def page_history():
    import pandas as pd

    st.title("📜 Recommendation History")

    recs = load_recommendations(limit=200)
    if not recs:
        st.info("No recommendation history yet.")
        return

    df = pd.DataFrame(recs)
    df["run_date"] = pd.to_datetime(df["run_date"])
    df = df.sort_values("run_date", ascending=False)

    # Filters
    col1, col2, col3 = st.columns(3)
    cap_filter = col1.multiselect(
        "Category", options=["SMALL", "LARGE"], default=["SMALL", "LARGE"]
    )
    status_filter = col2.multiselect(
        "Status", options=["OPEN", "CLOSED", "EXPIRED"],
        default=["OPEN", "CLOSED"]
    )
    days = col3.slider("Days back", 7, 180, 60)

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    mask = (
        df["cap_category"].isin(cap_filter)
        & df["status"].isin(status_filter)
        & (df["run_date"] >= cutoff)
    )
    df_filtered = df[mask].copy()

    if df_filtered.empty:
        st.info("No records match the filters.")
        return

    # Stats row
    closed = df_filtered[df_filtered["status"] == "CLOSED"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Picks", len(df_filtered))
    col2.metric("Closed", len(closed))
    if not closed.empty and closed["return_pct"].notna().any():
        wins = closed[closed["return_pct"] > 0]
        avg_ret = closed["return_pct"].mean()
        col3.metric("Win Rate", f"{len(wins)/len(closed)*100:.0f}%")
        col4.metric("Avg Return", f"{avg_ret:+.1f}%")
    else:
        col3.metric("Win Rate", "—")
        col4.metric("Avg Return", "—")

    st.divider()

    # Table
    display_cols = [
        "run_date", "symbol", "cap_category", "entry_price",
        "confidence_score", "status", "exit_price", "return_pct", "closed_at"
    ]
    display_df = df_filtered[display_cols].copy()
    display_df["run_date"] = display_df["run_date"].dt.date
    display_df["confidence_score"] = (display_df["confidence_score"] * 100).round(0)
    display_df.columns = [
        "Date", "Symbol", "Category", "Entry ₹",
        "Confidence %", "Status", "Exit ₹", "Return %", "Closed"
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )

    # Return distribution chart
    if not closed.empty and closed["return_pct"].notna().any():
        import plotly.express as px
        st.subheader("Return Distribution (Closed Positions)")
        fig = px.histogram(
            closed.dropna(subset=["return_pct"]),
            x="return_pct",
            nbins=20,
            color_discrete_sequence=["#0f3460"],
            title="Distribution of Returns (%)",
        )
        fig.add_vline(x=0, line_color="#e94560", line_dash="dash")
        fig.update_layout(
            xaxis_title="Return %",
            yaxis_title="Count",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)


# ─── PAGE: Portfolio ──────────────────────────────────────────────────────────

def page_portfolio():
    import pandas as pd

    st.title("📈 Paper Portfolio Performance")
    st.caption(
        "Hypothetical paper portfolio — no real money, no real trades. "
        "For research tracking only."
    )

    snapshots = load_portfolio_snapshots()
    if not snapshots:
        st.info("No portfolio snapshots yet. Run the daily pipeline to start tracking.")
        return

    df = pd.DataFrame(snapshots)
    df["date"] = pd.to_datetime(df["date"])

    latest = df.iloc[-1]
    settings_capital = 1_000_000.0

    # KPI row
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Portfolio Value", f"₹{latest['total']:,.0f}")
    col2.metric(
        "Total Return",
        f"{latest['return_pct']:+.1f}%",
        delta=f"vs NIFTY: {latest['alpha']:+.1f}%" if latest["alpha"] else None,
    )
    col3.metric("CAGR", f"{latest['cagr']:+.1f}%" if latest["cagr"] else "—")
    col4.metric(
        "Sharpe Ratio",
        f"{latest['sharpe']:.2f}" if latest["sharpe"] else "—"
    )
    col5.metric(
        "Win Rate",
        f"{latest['win_rate']*100:.0f}%" if latest["win_rate"] else "—"
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Max Drawdown", f"{latest['max_dd']:.1f}%" if latest["max_dd"] else "—")
    col2.metric("Open Positions", int(latest["open"]))
    col3.metric("Total Trades", int(latest["closed"]))

    st.divider()

    # Portfolio vs benchmark chart
    if len(df) > 1:
        import plotly.graph_objects as go

        st.subheader("Portfolio vs NIFTY 50 (Cumulative Return %)")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["return_pct"],
            name="Portfolio", line=dict(color="#0f3460", width=2),
            fill="tonexty" if len(df) > 2 else None,
        ))
        if df["nifty_return_pct"].notna().any():
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["nifty_return_pct"],
                name="NIFTY 50", line=dict(color="#e94560", width=2, dash="dot"),
            ))
        fig.add_hline(y=0, line_color="gray", line_dash="dash", line_width=1)
        fig.update_layout(
            yaxis_title="Return %",
            xaxis_title="Date",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        # Portfolio value chart
        st.subheader("Portfolio Value (₹)")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=df["date"], y=df["total"],
            name="Total Value", line=dict(color="#059669", width=2),
            fill="tozeroy", fillcolor="rgba(5,150,105,0.1)",
        ))
        fig2.add_hline(
            y=settings_capital,
            line_color="gray", line_dash="dash", line_width=1,
            annotation_text="Initial Capital",
        )
        fig2.update_layout(
            yaxis_title="Value (₹)",
            xaxis_title="Date",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Snapshot table
    with st.expander("Full snapshot history"):
        display = df[["date", "total", "return_pct", "nifty_return_pct", "alpha",
                       "max_dd", "sharpe", "open", "closed"]].copy()
        display.columns = [
            "Date", "Value ₹", "Return %", "NIFTY %", "Alpha %",
            "Max DD %", "Sharpe", "Open", "Closed"
        ]
        st.dataframe(display, use_container_width=True, hide_index=True)


# ─── Router ───────────────────────────────────────────────────────────────────

if page == "Overview":
    page_overview()
elif page == "History":
    page_history()
elif page == "Portfolio":
    page_portfolio()
