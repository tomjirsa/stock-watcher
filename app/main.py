# app/main.py
import json
import streamlit as st
import pandas as pd
from pathlib import Path

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
        strategy_filter = st.selectbox("Strategy", ["All", "MomentumStrategy", "FundamentalStrategy"])
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

        # Strategy performance summary
        st.subheader("Strategy Performance")
        stats_rows = []
        for name, stats in bt["strategies"].items():
            stats_rows.append({
                "Strategy": name,
                "Signals": stats["signal_count"],
                "Hit Rate 30d": f"{stats['hit_rate_30d']*100:.1f}%" if stats["hit_rate_30d"] is not None else "—",
                "Avg Return 30d": f"{stats['avg_return_30d']*100:.2f}%" if stats["avg_return_30d"] is not None else "—",
                "Avg Return 60d": f"{stats['avg_return_60d']*100:.2f}%" if stats["avg_return_60d"] is not None else "—",
                "Avg Return 90d": f"{stats['avg_return_90d']*100:.2f}%" if stats["avg_return_90d"] is not None else "—",
            })
        st.dataframe(pd.DataFrame(stats_rows), use_container_width=True)

        # Signal timeline
        st.subheader("Signal Timeline")
        signals_df = pd.DataFrame(bt["signals"])
        if signals_df.empty:
            st.info("No signals in backtest window.")
        else:
            signals_df["date"] = pd.to_datetime(signals_df["date"])
            ticker_filter = st.selectbox("Ticker", ["All"] + sorted(signals_df["ticker"].unique().tolist()))
            if ticker_filter != "All":
                signals_df = signals_df[signals_df["ticker"] == ticker_filter]

            st.dataframe(
                signals_df[["date", "ticker", "strategy", "score", "forward_return_30d", "forward_return_60d", "forward_return_90d"]],
                use_container_width=True,
            )
