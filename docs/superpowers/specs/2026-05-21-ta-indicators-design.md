# Technical Analysis Indicators — Design Spec

**Date:** 2026-05-21
**Status:** Approved

## Overview

Add technical analysis indicators to stock-watcher in two layers:

1. **Signal generation** — a new `TechnicalAnalysisStrategy` that scores stocks based on MACD, Bollinger Bands, RSI, and volume conditions.
2. **Chart overlays** — a 3-panel Plotly chart (price + BB + EMA, MACD, RSI) added to both the Signals tab drill-down and the Backtest tab single-ticker view.

## Indicators

| Indicator | Role |
|---|---|
| MACD(12,26,9) | Signal + chart panel |
| Bollinger Bands(20, 2σ) | Signal + price chart overlay |
| RSI(14) | Chart panel only (signal logic already in existing strategies) |
| EMA(configurable period) | Chart overlay only, period set via UI number input (default 20) |

VWAP was considered and excluded — it is an intraday indicator and cannot be computed meaningfully from daily OHLCV data.

## Architecture

### New file: `src/indicators.py`

Pure functions backed by `pandas-ta`. No side effects. Both strategies and the Streamlit app import from here.

```python
compute_macd(prices: pd.DataFrame) -> pd.DataFrame
    # returns columns: MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9

compute_bbands(prices: pd.DataFrame, length=20, std=2.0) -> pd.DataFrame
    # returns columns: BBU_20_2.0, BBM_20_2.0, BBL_20_2.0, BBB_20_2.0 (bandwidth)

compute_rsi(prices: pd.DataFrame, length=14) -> pd.Series

compute_ema(prices: pd.DataFrame, period: int) -> pd.Series
```

### New file: `src/strategies/technical.py`

`TechnicalAnalysisStrategy` replaces `MomentumStrategy`. Imports from `src/indicators.py`.

### Removed: `src/strategies/momentum.py`

`MomentumStrategy` is removed. Its signal logic (RSI, MA, volume) is superseded by `TechnicalAnalysisStrategy`. `GoldenCrossStrategy` and `FundamentalStrategy` are unchanged.

### Updated: `src/scanner.py`

Remove `MomentumStrategy`, add `TechnicalAnalysisStrategy` to the strategy list.

### Updated: `app/main.py`

- **Signals tab**: When a signal row is selected, show a price chart with TA overlays below the existing score + reasons text.
- **Backtest tab**: Refactor the existing single-ticker `go.Figure()` to `make_subplots(rows=3)` and add TA overlays alongside the existing buy/sell markers.

### Updated: `requirements.txt`

Add `pandas-ta`.

## Scoring — `TechnicalAnalysisStrategy`

Max score: 1.0. Returns `None` if score == 0.

| Condition | Points |
|---|---|
| MACD line crosses above signal line (bullish crossover today) | +0.30 |
| Price within 1% of lower Bollinger Band | +0.20 |
| RSI(14) between 50–70 | +0.20 |
| Volume ≥ 120% of 20-day average | +0.15 |
| Bollinger Band squeeze (bandwidth at 6-month low) | +0.15 |

Requires at least 26 bars of price history (MACD minimum). If `pandas-ta` returns `NaN` for a condition due to insufficient data, that condition is silently skipped.

## Chart Layout

Plotly `make_subplots(rows=3, shared_xaxes=True)` with `template="plotly_white"`.

| Row | Height | Content |
|---|---|---|
| 1 (60%) | Price line + Bollinger Bands overlay + EMA overlay |
| 2 (25%) | MACD histogram + MACD line + signal line + crossover marker |
| 3 (15%) | RSI(14) line with 30 (oversold) and 70 (overbought) reference lines |

All three panels share the x-axis — zoom and pan stay in sync.

**EMA period**: `st.number_input("EMA period", min_value=5, max_value=200, value=20, step=5)` rendered above the chart. Default 20. Changes re-render the chart immediately via Streamlit's reactive model.

**Buy/sell markers**: Shown in the Backtest tab only (single-ticker view). Not shown in the Signals tab chart.

## Data Flow

```
Scanner
  → DataService.get_price_history()  →  OHLCV DataFrame
  → StockData(ticker, prices, fundamentals)
  → TechnicalAnalysisStrategy.scan(stock)
        → compute_macd(prices)     ⎤
        → compute_bbands(prices)   ⎥  src/indicators.py
        → compute_rsi(prices)      ⎦
        → score each condition
        → return Signal | None

Streamlit (app/main.py)
  → load_price_history(ticker, start, end)   [existing cached function]
  → compute_macd(prices)    ⎤
  → compute_bbands(prices)  ⎥  src/indicators.py
  → compute_rsi(prices)     ⎥
  → compute_ema(prices, n)  ⎦
  → render Plotly make_subplots figure
```

`DataService` and `StockData` are unchanged.

## Error Handling

- `TechnicalAnalysisStrategy.scan()` returns `None` if fewer than 26 bars are available.
- `NaN` indicator values skip the scoring condition silently — score is lower, no exception raised.
- In the UI, if `load_price_history()` returns an empty DataFrame for a selected signal, display a `st.warning()` and omit the chart. Score and reasons still render.

## Testing

| File | What it tests |
|---|---|
| `tests/test_indicators.py` | Unit tests for each function in `src/indicators.py` with known price data — assert correct MACD/BBands/RSI/EMA values. No network calls. |
| `tests/test_technical_strategy.py` | `TechnicalAnalysisStrategy` with synthetic price DataFrames that trigger each scoring condition individually. Assert correct score and reasons text. |

Existing tests (`test_golden_cross.py`, `test_fundamental.py`, etc.) are unchanged. `test_momentum.py` is removed alongside `MomentumStrategy`.

## File Changes Summary

| File | Action |
|---|---|
| `src/indicators.py` | **New** |
| `src/strategies/technical.py` | **New** |
| `src/strategies/momentum.py` | **Deleted** |
| `src/scanner.py` | Updated — swap strategy |
| `app/main.py` | Updated — add chart panels to both tabs |
| `requirements.txt` | Updated — add `pandas-ta` |
| `tests/test_indicators.py` | **New** |
| `tests/test_technical_strategy.py` | **New** |
| `tests/test_momentum.py` | **Deleted** |
