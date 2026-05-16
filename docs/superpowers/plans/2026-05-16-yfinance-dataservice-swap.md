# yfinance DataService Swap — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Polygon.io data provider with yfinance so the scanner runs without an API key and processes all 19 watchlist tickers without rate limiting.

**Architecture:** `DataService` is the only class that changes — its public interface (`get_price_history`, `get_fundamentals`) stays identical. All callers (Scanner, Backtester, strategies) are unaffected. The existing disk cache is preserved unchanged.

**Tech Stack:** Python 3.11+, yfinance==1.3.0, pandas, pytest, pytest-mock

---

## File Map

| File | Change |
|---|---|
| `requirements.txt` | Remove `polygon-api-client`, remove `python-dotenv`, add `yfinance==1.3.0` |
| `src/data_service.py` | Full rewrite — yfinance replaces polygon, drop `api_key` param |
| `src/scanner.py` | Remove `request_delay`, simplify `__main__` |
| `src/backtester.py` | Simplify `__main__` |
| `tests/test_data_service.py` | Update mocks: yfinance instead of RESTClient |
| `.env.example` | Remove `POLYGON_API_KEY` |
| `.github/workflows/scan.yml` | Remove `POLYGON_API_KEY` secret reference |

---

## Task 1: Update dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Update `requirements.txt`**

Replace the entire file with:

```
yfinance==1.3.0
pandas==2.2.2
numpy==1.26.4
streamlit==1.35.0
pyyaml==6.0.1
pytest==8.2.0
pytest-mock==3.14.0
```

(Removes `polygon-api-client==1.14.2` and `python-dotenv==1.0.1`.)

- [ ] **Step 2: Install updated dependencies**

```bash
pip install -r requirements.txt
```

Expected: yfinance installs (already present), no errors.

- [ ] **Step 3: Verify yfinance import**

```bash
python -c "import yfinance as yf; print(yf.__version__)"
```

Expected: `1.3.0`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: swap polygon-api-client for yfinance, drop python-dotenv"
```

---

## Task 2: Rewrite DataService with yfinance (TDD)

**Files:**
- Modify: `src/data_service.py`
- Modify: `tests/test_data_service.py`

- [ ] **Step 1: Replace `tests/test_data_service.py` with failing tests**

```python
import pandas as pd
import pytest
from unittest.mock import MagicMock
from src.data_service import DataService

@pytest.fixture
def data_service(tmp_path):
    return DataService(cache_dir=str(tmp_path))

def test_get_price_history_returns_dataframe(data_service, mocker):
    mock_df = pd.DataFrame(
        {
            "Open": [100.0, 103.0],
            "High": [105.0, 108.0],
            "Low": [99.0, 102.0],
            "Close": [103.0, 106.0],
            "Volume": [1_000_000.0, 1_200_000.0],
        },
        index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
    )
    mocker.patch("yfinance.download", return_value=mock_df)
    df = data_service.get_price_history("NVDA", "2024-01-01", "2024-01-02")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 2

def test_get_price_history_uses_cache_on_second_call(data_service, mocker):
    mock_df = pd.DataFrame(
        {
            "Open": [100.0],
            "High": [105.0],
            "Low": [99.0],
            "Close": [103.0],
            "Volume": [1_000_000.0],
        },
        index=pd.to_datetime(["2024-01-01"]),
    )
    mock_download = mocker.patch("yfinance.download", return_value=mock_df)
    data_service.get_price_history("NVDA", "2024-01-01", "2024-01-01")
    data_service.get_price_history("NVDA", "2024-01-01", "2024-01-01")
    assert mock_download.call_count == 1

def test_get_fundamentals_returns_dict(data_service, mocker):
    mock_ticker = MagicMock()
    mock_ticker.info = {
        "trailingEps": 2.50,
        "totalRevenue": 5_000_000_000,
        "earningsGrowth": 0.20,
        "revenueGrowth": 0.15,
        "trailingPE": 25.0,
    }
    mocker.patch("yfinance.Ticker", return_value=mock_ticker)
    result = data_service.get_fundamentals("NVDA")
    assert isinstance(result, dict)
    assert "eps" in result
    assert "revenue" in result
    assert result["eps_growth"] == 0.20
    assert result["revenue_growth"] == 0.15

def test_get_fundamentals_returns_empty_dict_on_api_error(data_service, mocker):
    mocker.patch("yfinance.Ticker", side_effect=Exception("API error"))
    result = data_service.get_fundamentals("NVDA")
    assert result == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_data_service.py -v
```

Expected: 4 failures — `DataService.__init__` still requires `api_key`.

- [ ] **Step 3: Replace `src/data_service.py` with yfinance implementation**

```python
import json
import hashlib
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DataService:
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, key: str) -> Path:
        hashed = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hashed}.json"

    def _is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age = datetime.now().timestamp() - path.stat().st_mtime
        return age < 86400  # 24 hours

    def _read_cache(self, path: Path) -> dict | None:
        if self._is_fresh(path):
            return json.loads(path.read_text())
        return None

    def _write_cache(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data))

    def get_price_history(self, ticker: str, from_date: str, to_date: str) -> pd.DataFrame:
        cache_key = f"prices:{ticker}:{from_date}:{to_date}"
        cache_path = self._cache_path(cache_key)
        cached = self._read_cache(cache_path)
        if cached:
            return pd.DataFrame(cached["rows"], index=cached["index"])

        df = yf.download(ticker, start=from_date, end=to_date, auto_adjust=True, progress=False)
        if df.empty:
            raise ValueError(f"{ticker}: no price data returned")

        # Flatten MultiIndex columns produced by newer yfinance versions
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]]

        index = df.index.strftime("%Y-%m-%d").tolist()
        rows = df.to_dict("records")
        self._write_cache(cache_path, {"rows": rows, "index": index})
        return pd.DataFrame(rows, index=index)

    def get_fundamentals(self, ticker: str) -> dict:
        cache_key = f"fundamentals:{ticker}:{datetime.now().strftime('%Y-%m-%d')}"
        cache_path = self._cache_path(cache_key)
        cached = self._read_cache(cache_path)
        if cached:
            return cached

        try:
            info = yf.Ticker(ticker).info
            data = {
                "eps": info.get("trailingEps"),
                "revenue": info.get("totalRevenue"),
                "eps_growth": info.get("earningsGrowth"),
                "revenue_growth": info.get("revenueGrowth"),
                "pe_ratio": info.get("trailingPE"),
                "sector_median_pe": None,
            }
            self._write_cache(cache_path, data)
            return data
        except Exception as e:
            logger.warning(f"Failed to fetch fundamentals for {ticker}: {e}")
            return {}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_data_service.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Run full suite to check for regressions**

```bash
pytest tests/ -v
```

Expected: all 23 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/data_service.py tests/test_data_service.py
git commit -m "feat: swap DataService from Polygon.io to yfinance"
```

---

## Task 3: Simplify scanner.py and backtester.py

**Files:**
- Modify: `src/scanner.py`
- Modify: `src/backtester.py`

- [ ] **Step 1: Replace `src/scanner.py`**

```python
import json
import yaml
import logging
from datetime import date, timedelta
from pathlib import Path
from src.data_service import DataService
from src.models import StockData, Signal
from src.strategies.base import Strategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.fundamental import FundamentalStrategy

logger = logging.getLogger(__name__)

class Scanner:
    def __init__(self, data_service: DataService, results_dir: str = "results"):
        self.data_service = data_service
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.strategies: list[Strategy] = [
            MomentumStrategy(),
            FundamentalStrategy(),
        ]

    def run(self, tickers: list[str]) -> list[Signal]:
        today = str(date.today())
        from_date = str(date.today() - timedelta(days=400))
        signals = []

        for ticker in tickers:
            try:
                prices = self.data_service.get_price_history(ticker, from_date, today)
                fundamentals = self.data_service.get_fundamentals(ticker)
                stock = StockData(ticker=ticker, prices=prices, fundamentals=fundamentals)
            except Exception as e:
                logger.warning(f"Skipping {ticker}: {e}")
                continue

            for strategy in self.strategies:
                signal = strategy.scan(stock)
                if signal:
                    signals.append(signal)

        signals.sort(key=lambda s: s.score, reverse=True)
        self._write_results(signals, today)
        return signals

    def _write_results(self, signals: list[Signal], today: str) -> None:
        output = {
            "date": today,
            "signals": [
                {
                    "ticker": s.ticker,
                    "strategy": s.strategy,
                    "score": s.score,
                    "reasons": s.reasons,
                    "date": s.date,
                }
                for s in signals
            ],
        }
        path = self.results_dir / f"{today}.json"
        path.write_text(json.dumps(output, indent=2))
        logger.info(f"Wrote {len(signals)} signals to {path}")


def load_watchlist(path: str = "config/watchlist.yaml") -> list[str]:
    with open(path) as f:
        return yaml.safe_load(f)["tickers"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    service = DataService()
    scanner = Scanner(data_service=service)
    tickers = load_watchlist()
    signals = scanner.run(tickers)
    print(f"\nFound {len(signals)} signals:")
    for s in signals:
        print(f"  {s.ticker} [{s.strategy}] score={s.score}")
```

- [ ] **Step 2: Replace the `__main__` block in `src/backtester.py`**

Find and replace this exact block:

```python
if __name__ == "__main__":
    import os
    import yaml
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    api_key = os.environ["POLYGON_API_KEY"]
    service = DataService(api_key=api_key)
    backtester = Backtester(data_service=service)
    with open("config/watchlist.yaml") as f:
        tickers = yaml.safe_load(f)["tickers"]
    backtester.run(tickers)
    print("Backtest complete. Results written to results/backtest/latest.json")
```

Replace with:

```python
if __name__ == "__main__":
    import yaml
    logging.basicConfig(level=logging.INFO)

    service = DataService()
    backtester = Backtester(data_service=service)
    with open("config/watchlist.yaml") as f:
        tickers = yaml.safe_load(f)["tickers"]
    backtester.run(tickers)
    print("Backtest complete. Results written to results/backtest/latest.json")
```

- [ ] **Step 3: Remove `request_delay=0` from the scanner test fixture**

In `tests/test_scanner.py`, find and replace this line in the `scanner` fixture:

```python
    return Scanner(data_service=data_service, results_dir=str(tmp_path), request_delay=0)
```

Replace with:

```python
    return Scanner(data_service=data_service, results_dir=str(tmp_path))
```

- [ ] **Step 4: Run scanner tests**

```bash
pytest tests/test_scanner.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Run full suite**

```bash
pytest tests/ -v
```

Expected: all 23 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/scanner.py src/backtester.py tests/test_scanner.py
git commit -m "chore: remove rate-limit delay and POLYGON_API_KEY from scanner and backtester"
```

---

## Task 4: Update config files

**Files:**
- Modify: `.env.example`
- Modify: `.github/workflows/scan.yml`

- [ ] **Step 1: Replace `.env.example`**

```
# No API keys required — stock data is fetched via yfinance (Yahoo Finance)
```

- [ ] **Step 2: Replace `.github/workflows/scan.yml`**

```yaml
name: Nightly Stock Scan

on:
  schedule:
    - cron: "0 21 * * 1-5"  # 21:00 UTC Mon-Fri (after US market close)
  workflow_dispatch:          # allow manual trigger from GitHub UI

permissions:
  contents: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run scanner
        run: python src/scanner.py

      - name: Commit results
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add results/
          git diff --staged --quiet || git commit -m "chore: nightly scan $(date -u +%Y-%m-%d)"
          git push
```

- [ ] **Step 3: Verify workflow YAML is valid**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/scan.yml'))" && echo "Valid YAML"
```

Expected: `Valid YAML`

- [ ] **Step 4: Commit**

```bash
git add .env.example .github/workflows/scan.yml
git commit -m "chore: remove POLYGON_API_KEY from config and workflow"
```

---

## Task 5: Smoke test

- [ ] **Step 1: Run the full test suite one final time**

```bash
pytest tests/ -v
```

Expected: 23 tests PASS.

- [ ] **Step 2: Run the scanner live**

```bash
PYTHONPATH=. python src/scanner.py
```

Expected: scanner processes all 19 tickers, writes `results/YYYY-MM-DD.json`, prints found signals. No 429 errors. No "Skipping" warnings (unless a ticker genuinely has no data).

- [ ] **Step 3: Verify results file was written**

```bash
cat results/$(date +%Y-%m-%d).json
```

Expected: JSON with `date` and `signals` keys. Signals should include entries from both `MomentumStrategy` and `FundamentalStrategy` (not just Momentum as before).
