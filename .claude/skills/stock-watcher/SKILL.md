---
name: stock-watcher
description: Use when asked to run the stock scanner, backtest, tests, or Streamlit app for the stock-watcher project
---

# Stock Watcher — Run Commands

All commands require the virtual environment. Always prefix with `source .venv/bin/activate &&`.

## Run the Scanner

Fetches price + fundamental data for all 19 watchlist tickers and writes signals to `results/YYYY-MM-DD.json`.

```bash
source .venv/bin/activate && PYTHONPATH=. python src/scanner.py
```

**Expected output:** list of signals sorted by score. SQ may be skipped (possibly delisted — that's normal).

**Results file:**
```bash
cat results/$(date +%Y-%m-%d).json
```

## Run the Backtest

Walk-forward 2-year backtest across all watchlist tickers, writes to `results/backtest/latest.json`.

```bash
source .venv/bin/activate && PYTHONPATH=. python src/backtester.py
```

## Run the Streamlit App

Launches the UI at http://localhost:8501. Two tabs: Signals (filter/sort) and Backtest (strategy stats).

```bash
source .venv/bin/activate && streamlit run app/main.py
```

## Run Tests

```bash
# Full suite (29 tests)
source .venv/bin/activate && pytest tests/ -v

# Single strategy
source .venv/bin/activate && pytest tests/test_golden_cross.py -v
source .venv/bin/activate && pytest tests/test_momentum.py -v
source .venv/bin/activate && pytest tests/test_fundamental.py -v

# Scanner and data service
source .venv/bin/activate && pytest tests/test_scanner.py tests/test_data_service.py -v
```

## Watchlist

19 tickers in `config/watchlist.yaml`:
NVDA, AMD, AVGO, TSM, MSFT, CRM, SNOW, DDOG, LLY, ISRG, DXCM, AMZN, SHOP, MELI, V, SQ, NU, TSLA, ENPH

## Strategies

| Strategy | Signal | Max Score |
|---|---|---|
| `GoldenCrossStrategy` | MA50 crossed above MA200 within 20 trading days | 1.0 (decays to 0.5) |
| `MomentumStrategy` | MA trend + RSI 50-70 + volume spike | 1.0 |
| `FundamentalStrategy` | EPS growth >15% + revenue growth >10% | 0.75 (P/E condition dormant) |

**Best 6M entry candidates:** stocks appearing in all three strategies, especially with `GoldenCrossStrategy` score > 0.8.

## Data

- Price history and fundamentals fetched via **yfinance** — no API key required
- Disk cache at `data/cache/` (24h freshness) — re-runs same day are instant
- Cache is gitignored; delete it to force a fresh fetch
