# Stock Watcher — Data Service & Strategies Design

**Date:** 2026-05-15
**Scope:** Data service, strategy framework, scanner, backtester, GitHub Actions scheduling, Streamlit explorer

---

## Overview

A Python tool that periodically scans a user-defined watchlist for stocks with growth potential using a combination of technical and fundamental signals. GitHub Actions runs the scanner nightly and commits results to the repo. A local Streamlit app lets the user explore scan results and backtest strategy performance interactively.

---

## Project Structure

```
stock-watcher/
├── config/
│   └── watchlist.yaml          # user-defined tickers + ~20 default promising stocks
├── data/
│   └── cache/                  # polygon.io responses cached as JSON (gitignored)
├── results/
│   ├── YYYY-MM-DD.json         # nightly scan outputs committed by GH Actions
│   └── backtest/
│       └── latest.json         # most recent backtest run (manual trigger)
├── src/
│   ├── data_service.py         # DataService class — all Polygon.io interaction
│   ├── models.py               # Signal, StockData dataclasses
│   ├── strategies/
│   │   ├── base.py             # Strategy ABC
│   │   ├── momentum.py         # technical: MA crossover + RSI + volume
│   │   └── fundamental.py      # fundamental: EPS growth + revenue growth + P/E
│   ├── scanner.py              # orchestrates DataService + strategies → results
│   └── backtester.py           # replays 2-year historical snapshots through strategies
├── app/
│   └── main.py                 # Streamlit explorer (Signals tab + Backtest tab)
├── .github/workflows/
│   └── scan.yml                # nightly scheduled GH Actions job
└── requirements.txt
```

---

## Data Source

**Polygon.io** — free tier provides unlimited historical EOD (end-of-day) OHLCV bars and fundamentals. API key stored as a GitHub Actions secret (`POLYGON_API_KEY`) and locally in a `.env` file (gitignored).

---

## Models (`src/models.py`)

```python
@dataclass
class StockData:
    ticker: str
    prices: pd.DataFrame     # columns: open, high, low, close, volume; index: date
    fundamentals: dict       # keys: eps_growth, revenue_growth, pe_ratio, etc.

@dataclass
class Signal:
    ticker: str
    strategy: str            # name of the strategy that fired
    score: float             # 0.0–1.0 composite score
    reasons: list[str]       # human-readable explanation of why the signal fired
    date: str                # ISO date of the scan
```

---

## Data Service (`src/data_service.py`)

`DataService` wraps Polygon.io with fetching and disk caching. Raw responses are persisted to `data/cache/` as JSON keyed by ticker + date range, so the backtester can replay history without re-hitting the API and GitHub Actions never fetches duplicate data within a run.

```python
class DataService:
    def get_price_history(ticker: str, from_date: str, to_date: str) -> pd.DataFrame
    def get_fundamentals(ticker: str) -> dict
```

Cache invalidation: cache entries are considered fresh for 24 hours. Stale entries are re-fetched transparently.

---

## Strategy Framework (`src/strategies/`)

### Base class (`base.py`)

```python
class Strategy(ABC):
    @abstractmethod
    def scan(self, stock: StockData) -> Signal | None:
        # Return a Signal if the stock meets criteria, None otherwise
```

Adding a new strategy requires only:
1. A new file in `strategies/` implementing `Strategy`
2. Adding it to the strategy list in `scanner.py`

The scanner, backtester, and Streamlit app all operate on the `Signal` interface and require no changes.

### `MomentumStrategy` (`strategies/momentum.py`) — technical signals

| Signal | Condition | Weight |
|---|---|---|
| Golden cross | 50-day MA crosses above 200-day MA | 40% |
| RSI | Between 50 and 70 (trending, not overbought) | 30% |
| Volume | 20% above 20-day average | 30% |

Score is the weighted sum of passing conditions (each condition contributes its weight if met, 0 otherwise).

### `FundamentalStrategy` (`strategies/fundamental.py`) — fundamental signals

| Signal | Condition | Weight |
|---|---|---|
| EPS growth | > 15% YoY | 40% |
| Revenue growth | > 10% YoY | 35% |
| P/E ratio | Below sector median | 25% |

Score is the weighted sum of passing conditions.

A stock can produce signals from both strategies independently. No combining or averaging between strategies.

---

## Scanner (`src/scanner.py`)

Orchestration entrypoint for nightly runs:

1. Load tickers from `config/watchlist.yaml`
2. Fetch `StockData` for all tickers via `DataService`
3. Run all registered strategies against each `StockData`
4. Collect non-`None` signals, sort by score descending
5. Write output to `results/YYYY-MM-DD.json`

---

## Backtester (`src/backtester.py`)

Manual local trigger only: `python src/backtester.py`

1. Fetch 2 years of price history and fundamentals for all watchlist tickers
2. Walk forward day-by-day, building a `StockData` snapshot at each point
3. Run all strategies on each snapshot — record date and score when a signal fires
4. Compute forward returns at 30, 60, and 90 days after each signal
5. Write summary to `results/backtest/latest.json`

Output includes per-strategy: hit rate, average forward return at each horizon, and best/worst individual calls.

---

## Watchlist (`config/watchlist.yaml`)

User-editable list of tickers. Ships with ~20 default stocks across sectors with strong historical growth profiles:

- **Semiconductors:** NVDA, AMD, AVGO, TSM
- **Cloud/Software:** MSFT, CRM, SNOW, DDOG
- **Healthcare/Biotech:** LLY, ISRG, DXCM
- **Consumer/E-commerce:** AMZN, SHOP, MELI
- **Financials/Fintech:** V, SQ, NU
- **EV/Clean Energy:** TSLA, ENPH

---

## GitHub Actions (`.github/workflows/scan.yml`)

- **Schedule:** nightly at 21:00 UTC (after US market close)
- **Steps:** checkout repo → install dependencies → run `scanner.py` → commit `results/YYYY-MM-DD.json` back to repo
- **Secret:** `POLYGON_API_KEY` stored in GitHub Actions secrets

---

## Streamlit Explorer (`app/main.py`)

Run locally with `streamlit run app/main.py`. Reads from `results/` — no live API calls.

### Signals Tab
- **Sidebar:** date picker (select scan run), strategy filter, minimum score slider
- **Main panel:** ranked table — ticker, strategy, score, reasons
- **Detail view:** click a ticker → 30-day OHLCV price chart, fundamental summary, full reasons list

### Backtest Tab
- **Strategy performance table:** hit rate, avg 30/60/90-day forward return, signal count per strategy
- **Signal timeline chart:** when each strategy fired on each ticker over the 2-year window
- **Per-ticker drill-down:** price chart with signal dates overlaid, forward return annotations

---

## Error Handling

- Polygon.io API errors: log and skip the ticker for that run, do not fail the entire scan
- Missing fundamentals data: `FundamentalStrategy` returns `None` for that ticker
- Empty results: write an empty signals array to the results file, do not commit a broken JSON

---

## Dependencies

```
polygon-api-client
pandas
numpy
streamlit
python-dotenv
pyyaml
```
