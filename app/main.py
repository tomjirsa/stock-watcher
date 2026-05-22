# app/main.py
import json
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from pathlib import Path


@st.cache_data(show_spinner=False)
def load_price_history(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    df.index = pd.to_datetime(df.index)
    return df

RESULTS_DIR = Path("results")
BACKTEST_PATH = RESULTS_DIR / "backtest" / "latest.json"

st.set_page_config(page_title="Stock Watcher", layout="wide")

@st.cache_data
def load_scan_results(date_str: str) -> dict:
    path = RESULTS_DIR / f"{date_str}.json"
    if not path.exists():
        return {"signals": []}
    return json.loads(path.read_text())

@st.cache_data
def load_backtest_results() -> dict | None:
    if not BACKTEST_PATH.exists():
        return None
    return json.loads(BACKTEST_PATH.read_text())

def get_available_dates() -> list[str]:
    files = sorted(RESULTS_DIR.glob("????-??-??.json"), reverse=True)
    return [f.stem for f in files]

tab_signals, tab_backtest = st.tabs(["Signals", "Backtest"])

with tab_signals:
    st.header("Stock Signals")

    dates = get_available_dates()
    if not dates:
        st.info("No scan results found. Run the scanner first: `python src/scanner.py`")
        st.stop()

    with st.sidebar:
        st.subheader("Filters")
        selected_date = st.selectbox("Scan date", dates)
        strategy_filter = st.selectbox("Strategy", ["All", "GoldenCrossStrategy", "MomentumStrategy", "FundamentalStrategy"])
        min_score = st.slider("Minimum score", 0.0, 1.0, 0.0, 0.05)

    data = load_scan_results(selected_date)
    signals = data.get("signals", [])

    if strategy_filter != "All":
        signals = [s for s in signals if s["strategy"] == strategy_filter]
    signals = [s for s in signals if s["score"] >= min_score]

    if not signals:
        st.info("No signals match the current filters.")
    else:
        df = pd.DataFrame(signals)[["ticker", "strategy", "score", "reasons"]]
        df["reasons"] = df["reasons"].apply(lambda r: " | ".join(r))

        selected_rows = st.dataframe(
            df,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
        )

        if selected_rows and selected_rows.selection.rows:
            idx = selected_rows.selection.rows[0]
            signal = signals[idx]
            st.divider()
            st.subheader(f"{signal['ticker']} — {signal['strategy']}")
            st.metric("Score", f"{signal['score']:.2f}")
            st.write("**Why this signal fired:**")
            for reason in signal["reasons"]:
                st.write(f"- {reason}")

with tab_backtest:
    st.header("Backtest Results")

    bt = load_backtest_results()
    if bt is None:
        st.info("No backtest results found. Run: `python src/backtester.py`")
    else:
        st.caption(f"Generated: {bt.get('generated', 'unknown')}")

        trades_raw = bt.get("trades", [])
        bt_config = bt.get("config", {})

        if not trades_raw:
            st.info("No trades found. Run: `python src/backtester.py`")
        else:
            trades_df = pd.DataFrame(trades_raw)
            trades_df["date"] = pd.to_datetime(trades_df["entry_date"])
            trades_df["month"] = trades_df["date"].dt.to_period("M").dt.to_timestamp()

            # --- Config + investment input ---
            col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
            with col_cfg1:
                st.metric("Hold Period", f"{bt_config.get('hold_days', 90)} days",
                          help="Days between re-entries. Edit config/backtest.yaml and re-run to change.")
            with col_cfg2:
                investment = st.number_input(
                    "Investment per trade ($)",
                    min_value=1.0,
                    value=float(bt_config.get("investment_per_trade", 1000.0)),
                    step=100.0,
                )
            with col_cfg3:
                horizon = st.radio("Return horizon", ["30d", "60d", "90d"], horizontal=True, index=2)

            return_col = f"forward_return_{horizon}"

            st.divider()

            # --- Strategy Performance table ---
            st.subheader("Strategy Performance")
            perf_ticker = st.selectbox(
                "Filter by ticker",
                ["All"] + sorted(trades_df["ticker"].unique().tolist()),
                key="perf_ticker",
            )
            perf_df = trades_df if perf_ticker == "All" else trades_df[trades_df["ticker"] == perf_ticker]

            stats_rows = []
            for strategy, grp in perf_df.groupby("strategy"):
                v30 = grp["forward_return_30d"].dropna()
                v60 = grp["forward_return_60d"].dropna()
                v90 = grp["forward_return_90d"].dropna()
                vh = grp[return_col].dropna()
                total_profit = (investment * vh).sum()
                stats_rows.append({
                    "Strategy": strategy,
                    "Trades": len(grp),
                    "Win Rate 30d": f"{(v30 > 0).mean()*100:.1f}%" if len(v30) else "—",
                    "Win Rate 60d": f"{(v60 > 0).mean()*100:.1f}%" if len(v60) else "—",
                    "Win Rate 90d": f"{(v90 > 0).mean()*100:.1f}%" if len(v90) else "—",
                    "Avg Return 30d": f"{v30.mean()*100:.2f}%" if len(v30) else "—",
                    "Avg Return 60d": f"{v60.mean()*100:.2f}%" if len(v60) else "—",
                    "Avg Return 90d": f"{v90.mean()*100:.2f}%" if len(v90) else "—",
                    f"Total P&L ({horizon})": f"${total_profit:+,.0f}" if len(vh) else "—",
                })
            st.dataframe(pd.DataFrame(stats_rows), use_container_width=True)

            with st.expander("What do these columns mean?"):
                st.markdown(f"""
**Trades** — Number of unique entry points after deduplication. Once a signal fires, the strategy waits {bt_config.get('hold_days', 90)} days before re-entering the same stock.

**Win Rate 30d / 60d / 90d** — Percentage of trades where the stock was *higher* at exit. 50% = random chance. Above 55% is meaningful edge.

**Avg Return 30d / 60d / 90d** — Mean price change at each horizon across all trades. Positive = strategy tended to fire before the stock went up.

**Total P&L ({horizon})** — Sum of (investment × return) for all trades at the selected horizon. Shows the actual dollar outcome if you had invested ${investment:,.0f} on every signal.

> **How to read them together:** High win rate + high avg return = reliable, consistent signal. High avg return + low win rate = a few big winners skew the average — more volatile outcome.
                """)

            st.divider()

            # --- P&L summary metrics ---
            valid = trades_df[trades_df[return_col].notna()].copy()
            valid["profit"] = investment * valid[return_col]
            total_trades = len(valid)
            total_invested = investment * total_trades
            total_profit = valid["profit"].sum()
            win_rate = (valid["profit"] > 0).mean() * 100

            st.subheader(f"Overall P&L Summary ({horizon})")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Trades", total_trades)
            m2.metric("Total Invested", f"${total_invested:,.0f}")
            m3.metric("Total P&L", f"${total_profit:+,.0f}",
                      delta=f"{(total_profit / total_invested * 100):+.1f}%" if total_invested else None)
            m4.metric("Win Rate", f"{win_rate:.1f}%")

            st.divider()

            # --- Chart controls ---
            col_strategy_bt, col_ticker_bt = st.columns(2)
            with col_strategy_bt:
                bt_strategy_filter = st.selectbox(
                    "Strategy",
                    ["All"] + sorted(trades_df["strategy"].unique().tolist()),
                    key="bt_strategy",
                )
            with col_ticker_bt:
                bt_ticker_filter = st.selectbox(
                    "Ticker",
                    ["All"] + sorted(trades_df["ticker"].unique().tolist()),
                    key="bt_ticker",
                )

            chart_df = trades_df.copy()
            if bt_strategy_filter != "All":
                chart_df = chart_df[chart_df["strategy"] == bt_strategy_filter]
            if bt_ticker_filter != "All":
                chart_df = chart_df[chart_df["ticker"] == bt_ticker_filter]

            # --- Chart 1: Avg monthly return over time ---
            st.subheader(f"Avg {horizon} Return by Month")
            monthly_return = (
                chart_df.groupby(["month", "strategy"])[return_col]
                .mean()
                .mul(100)
                .reset_index()
                .pivot(index="month", columns="strategy", values=return_col)
            )
            monthly_return.index = monthly_return.index.strftime("%Y-%m")
            st.line_chart(monthly_return, use_container_width=True)

            # --- Chart 2: Trade count per month ---
            st.subheader("Trade Count by Month")
            count_group_col = "ticker" if bt_ticker_filter == "All" else "strategy"
            monthly_count = (
                chart_df.groupby(["month", count_group_col])
                .size()
                .reset_index(name="count")
                .pivot(index="month", columns=count_group_col, values="count")
                .fillna(0)
            )
            monthly_count.index = monthly_count.index.strftime("%Y-%m")
            st.bar_chart(monthly_count, use_container_width=True)

            # --- Chart 3: Per-ticker avg return with own horizon selector ---
            if bt_ticker_filter == "All":
                st.subheader("Avg Return by Ticker")
                ticker_horizon = st.radio(
                    "Horizon", ["30d", "60d", "90d"], horizontal=True, index=2, key="ticker_horizon"
                )
                ticker_return_col = f"forward_return_{ticker_horizon}"
                ticker_return = (
                    chart_df.groupby("ticker")[ticker_return_col]
                    .mean()
                    .mul(100)
                    .sort_values(ascending=False)
                    .rename("avg_return_%")
                )
                st.bar_chart(ticker_return, use_container_width=True)

            # --- Trade Timeline Chart + Table ---
            st.subheader("Trade Timeline")
            exit_date_col = f"exit_date_{horizon}"
            table_df = chart_df.copy()
            table_df["profit"] = (investment * table_df[return_col]).where(table_df[return_col].notna())

            if not table_df.empty:
                if bt_ticker_filter == "All":
                    # Gantt: one row per ticker, bars coloured by P&L
                    gantt_rows = []
                    for _, t in table_df.iterrows():
                        p = t.get("profit")
                        ret = t.get(return_col)
                        exit_d = t.get(exit_date_col) or t["entry_date"]
                        status = "Profit" if pd.notna(p) and p > 0 else ("Loss" if pd.notna(p) else "Pending")
                        gantt_rows.append({
                            "Ticker": t["ticker"],
                            "Strategy": t["strategy"],
                            "Start": t["entry_date"],
                            "Finish": exit_d,
                            "Return": f"{ret*100:+.1f}%" if pd.notna(ret) else "N/A",
                            "Profit ($)": f"${p:+,.0f}" if pd.notna(p) else "N/A",
                            "Status": status,
                        })
                    gdf = pd.DataFrame(gantt_rows)
                    gdf["Start"] = pd.to_datetime(gdf["Start"])
                    gdf["Finish"] = pd.to_datetime(gdf["Finish"])
                    fig_gantt = px.timeline(
                        gdf,
                        x_start="Start", x_end="Finish", y="Ticker",
                        color="Status",
                        color_discrete_map={"Profit": "#2ecc71", "Loss": "#e74c3c", "Pending": "#95a5a6"},
                        hover_data={"Strategy": True, "Return": True, "Profit ($)": True, "Status": False,
                                    "Start": False, "Finish": False},
                        title="Trade Periods by Ticker",
                    )
                    fig_gantt.update_layout(
                        height=max(350, gdf["Ticker"].nunique() * 28 + 120),
                        xaxis_title="Date", yaxis_title="",
                    )
                    st.plotly_chart(fig_gantt, use_container_width=True)

                else:
                    # Price chart with buy/sell overlays for selected ticker
                    min_date = table_df["entry_date"].min()
                    raw_max = pd.to_datetime(table_df[exit_date_col].max()) if exit_date_col in table_df else pd.Timestamp.now()
                    max_date = (raw_max + pd.Timedelta(days=10)).strftime("%Y-%m-%d")

                    with st.spinner(f"Loading {bt_ticker_filter} price history…"):
                        prices = load_price_history(bt_ticker_filter, min_date, max_date)

                    fig = go.Figure()

                    if not prices.empty:
                        fig.add_trace(go.Scatter(
                            x=prices.index, y=prices["close"],
                            mode="lines", name="Price",
                            line=dict(color="#3498db", width=1.5),
                            hovertemplate="%{x|%Y-%m-%d}: $%{y:.2f}<extra></extra>",
                        ))

                    for _, t in table_df.iterrows():
                        entry_dt = pd.to_datetime(t["entry_date"])
                        exit_dt = pd.to_datetime(t.get(exit_date_col)) if t.get(exit_date_col) else None
                        ret = t.get(return_col)
                        p = t.get("profit")
                        is_profit = pd.notna(p) and p > 0
                        bar_color = "#2ecc71" if is_profit else ("#e74c3c" if pd.notna(p) else "#95a5a6")

                        # Resolve entry price
                        entry_price = None
                        if not prices.empty:
                            idx = prices.index.get_indexer([entry_dt], method="nearest")[0]
                            if idx >= 0:
                                entry_price = float(prices["close"].iloc[idx])

                        # Resolve sell price
                        sell_price = None
                        if entry_price and pd.notna(ret):
                            sell_price = entry_price * (1 + ret)
                        elif not prices.empty and exit_dt is not None:
                            idx = prices.index.get_indexer([exit_dt], method="nearest")[0]
                            if idx >= 0:
                                sell_price = float(prices["close"].iloc[idx])

                        # Shaded hold period
                        if exit_dt:
                            fig.add_vrect(
                                x0=entry_dt, x1=exit_dt,
                                fillcolor=bar_color, opacity=0.12,
                                layer="below", line_width=0,
                            )

                        # Buy marker
                        if entry_price is not None:
                            fig.add_trace(go.Scatter(
                                x=[entry_dt], y=[entry_price],
                                mode="markers", name="Buy",
                                marker=dict(symbol="triangle-up", color="#2ecc71", size=14,
                                            line=dict(width=1, color="darkgreen")),
                                hovertemplate=(
                                    f"<b>BUY {bt_ticker_filter}</b><br>"
                                    f"Date: {t['entry_date']}<br>"
                                    f"Strategy: {t['strategy']}<br>"
                                    f"Score: {t['score']:.2f}<br>"
                                    f"Price: ${entry_price:.2f}"
                                    "<extra></extra>"
                                ),
                                showlegend=False,
                            ))

                        # Sell marker
                        if sell_price is not None and exit_dt is not None:
                            ret_str = f"{ret*100:+.1f}%" if pd.notna(ret) else "N/A"
                            profit_str = f"${p:+,.2f}" if pd.notna(p) else "N/A"
                            fig.add_trace(go.Scatter(
                                x=[exit_dt], y=[sell_price],
                                mode="markers", name="Sell",
                                marker=dict(symbol="triangle-down", color="#e74c3c", size=14,
                                            line=dict(width=1, color="darkred")),
                                hovertemplate=(
                                    f"<b>SELL {bt_ticker_filter}</b><br>"
                                    f"Date: {t.get(exit_date_col)}<br>"
                                    f"Price: ${sell_price:.2f}<br>"
                                    f"Return: {ret_str}<br>"
                                    f"<b>Profit: {profit_str}</b>"
                                    "<extra></extra>"
                                ),
                                showlegend=False,
                            ))

                    # Single legend entries
                    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                        marker=dict(symbol="triangle-up", color="#2ecc71", size=12), name="Buy"))
                    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                        marker=dict(symbol="triangle-down", color="#e74c3c", size=12), name="Sell"))

                    fig.update_layout(
                        title=f"{bt_ticker_filter} — Trade History ({horizon} hold)",
                        xaxis_title="Date", yaxis_title="Price ($)",
                        hovermode="closest", height=480,
                    )
                    st.plotly_chart(fig, use_container_width=True)

            # Table below chart
            display_cols = ["entry_date", exit_date_col, "ticker", "strategy", "score", return_col, "profit"]
            display_cols = [c for c in display_cols if c in table_df.columns]
            st.dataframe(
                table_df[display_cols].sort_values("entry_date", ascending=False),
                use_container_width=True,
            )
