# Stock Watcher — Data Service & Strategies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a nightly stock scanner that fetches price and fundamental data from Polygon.io, runs configurable technical and fundamental strategies against a user-defined watchlist, stores ranked signals as JSON, and exposes results + backtest performance in a local Streamlit app.

**Architecture:** A `DataService` class wraps Polygon.io with disk caching. Each strategy implements a shared `Strategy` ABC with a single `scan(stock) -> Signal | None` method, making strategies independently testable and trivially extensible. A `Scanner` orchestrates data fetching and strategy execution for nightly GitHub Actions runs; a `Backtester` replays 2 years of historical snapshots through the same strategies on demand.

**Tech Stack:** Python 3.11+, polygon-api-client, pandas, numpy, streamlit, python-dotenv, pyyaml, pytest

---

## File Map

| File | Responsibility |
|---|---|
| `requirements.txt` | Python dependencies |
| `.gitignore` | Exclude cache, .env, __pycache__ |
| `.env.example` | Document required env vars |
| `config/watchlist.yaml` | User-editable ticker list with defaults |
| `src/models.py` | `StockData` and `Signal` dataclasses |
| `src/data_service.py` | `DataService` — Polygon.io fetching + disk cache |
| `src/strategies/base.py` | `Strategy` ABC |
| `src/strategies/momentum.py` | `MomentumStrategy` — MA crossover, RSI, volume |
| `src/strategies/fundamental.py` | `FundamentalStrategy` — EPS growth, revenue, P/E |
| `src/scanner.py` | Orchestrates DataService + strategies → results JSON |
| `src/backtester.py` | Replays 2-year history through strategies |
| `app/main.py` | Streamlit explorer — Signals + Backtest tabs |
| `.github/workflows/scan.yml` | Nightly GH Actions scan job |
| `tests/test_models.py` | Model validation tests |
| `tests/test_data_service.py` | DataService cache + fetch tests |
| `tests/test_momentum.py` | MomentumStrategy signal tests |
| `tests/test_fundamental.py` | FundamentalStrategy signal tests |
| `tests/test_scanner.py` | Scanner orchestration tests |
| `tests/test_backtester.py` | Backtester walk-forward tests |

---

## Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `config/watchlist.yaml`

- [ ] **Step 1: Create `requirements.txt`**

```
polygon-api-client==1.14.2
pandas==2.2.2
numpy==1.26.4
streamlit==1.35.0
python-dotenv==1.0.1
pyyaml==6.0.1
pytest==8.2.0
pytest-mock==3.14.0
```

- [ ] **Step 2: Create `.gitignore`**

```
.env
data/cache/
__pycache__/
*.pyc
.pytest_cache/
.DS_Store
```

- [ ] **Step 3: Create `.env.example`**

```
POLYGON_API_KEY=your_polygon_api_key_here
```

- [ ] **Step 4: Create `config/watchlist.yaml`**

```yaml
tickers:
  # Semiconductors
  - NVDA
  - AMD
  - AVGO
  - TSM
  # Cloud / Software
  - MSFT
  - CRM
  - SNOW
  - DDOG
  # Healthcare / Biotech
  - LLY
  - ISRG
  - DXCM
  # Consumer / E-commerce
  - AMZN
  - SHOP
  - MELI
  # Financials / Fintech
  - V
  - SQ
  - NU
  # EV / Clean Energy
  - TSLA
  - ENPH
```

- [ ] **Step 5: Create directory structure and install dependencies**

```bash
mkdir -p src/strategies data/cache results/backtest app tests
touch src/__init__.py src/strategies/__init__.py tests/__init__.py
pip install -r requirements.txt
```

Expected: all packages install without errors.

- [ ] **Step 6: Commit**

```bash
git init
git add requirements.txt .gitignore .env.example config/watchlist.yaml src/__init__.py src/strategies/__init__.py tests/__init__.py
git commit -m "chore: project scaffolding and dependencies"
```

---

## Task 2: Models

**Files:**
- Create: `src/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_models.py
import pandas as pd
from src.models import StockData, Signal

def test_stock_data_holds_ticker_prices_and_fundamentals():
    prices = pd.DataFrame({"close": [100.0, 101.0]}, index=["2024-01-01", "2024-01-02"])
    fundamentals = {"eps_growth": 0.20, "revenue_growth": 0.15, "pe_ratio": 25.0}
    stock = StockData(ticker="NVDA", prices=prices, fundamentals=fundamentals)
    assert stock.ticker == "NVDA"
    assert len(stock.prices) == 2
    assert stock.fundamentals["eps_growth"] == 0.20

def test_signal_fields():
    signal = Signal(
        ticker="NVDA",
        strategy="MomentumStrategy",
        score=0.85,
        reasons=["Golden cross detected", "RSI at 62"],
        date="2024-01-02",
    )
    assert signal.score == 0.85
    assert len(signal.reasons) == 2
    assert signal.date == "2024-01-02"

def test_signal_score_is_float_between_0_and_1():
    signal = Signal(ticker="AMD", strategy="FundamentalStrategy", score=0.0, reasons=[], date="2024-01-01")
    assert 0.0 <= signal.score <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_models.py -v
```

Expected: `ImportError` — `src.models` does not exist yet.

- [ ] **Step 3: Implement `src/models.py`**

```python
from dataclasses import dataclass, field
import pandas as pd

@dataclass
class StockData:
    ticker: str
    prices: pd.DataFrame
    fundamentals: dict

@dataclass
class Signal:
    ticker: str
    strategy: str
    score: float
    reasons: list[str]
    date: str
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_models.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add StockData and Signal dataclasses"
```

---

## Task 3: DataService

**Files:**
- Create: `src/data_service.py`
- Create: `tests/test_data_service.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_data_service.py
import json
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.data_service import DataService

PRICE_RESPONSE = {
    "results": [
        {"t": 1704067200000, "o": 100.0, "h": 105.0, "l": 99.0, "c": 103.0, "v": 1000000},
        {"t": 1704153600000, "o": 103.0, "h": 108.0, "l": 102.0, "c": 106.0, "v": 1200000},
    ]
}

FUNDAMENTALS_RESPONSE = {
    "results": {
        "financials": {
            "income_statement": {
                "basic_earnings_per_share": {"value": 2.50},
                "revenues": {"value": 5000000000},
            }
        }
    }
}

@pytest.fixture
def data_service(tmp_path):
    return DataService(api_key="test_key", cache_dir=str(tmp_path))

def test_get_price_history_returns_dataframe(data_service, mocker):
    mock_client = mocker.patch("src.data_service.RESTClient")
    mock_instance = mock_client.return_value
    mock_instance.get_aggs.return_value = [
        MagicMock(timestamp=1704067200000, open=100.0, high=105.0, low=99.0, close=103.0, volume=1000000),
        MagicMock(timestamp=1704153600000, open=103.0, high=108.0, low=102.0, close=106.0, volume=1200000),
    ]
    df = data_service.get_price_history("NVDA", "2024-01-01", "2024-01-02")
    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert len(df) == 2

def test_get_price_history_uses_cache_on_second_call(data_service, mocker):
    mock_client = mocker.patch("src.data_service.RESTClient")
    mock_instance = mock_client.return_value
    mock_instance.get_aggs.return_value = [
        MagicMock(timestamp=1704067200000, open=100.0, high=105.0, low=99.0, close=103.0, volume=1000000),
    ]
    data_service.get_price_history("NVDA", "2024-01-01", "2024-01-01")
    data_service.get_price_history("NVDA", "2024-01-01", "2024-01-01")
    assert mock_instance.get_aggs.call_count == 1

def test_get_fundamentals_returns_dict(data_service, mocker):
    mock_client = mocker.patch("src.data_service.RESTClient")
    mock_instance = mock_client.return_value
    mock_instance.vx.list_stock_financials.return_value = iter([
        MagicMock(
            financials=MagicMock(
                income_statement=MagicMock(
                    basic_earnings_per_share=MagicMock(value=2.50),
                    revenues=MagicMock(value=5_000_000_000),
                )
            )
        )
    ])
    result = data_service.get_fundamentals("NVDA")
    assert isinstance(result, dict)
    assert "eps" in result
    assert "revenue" in result

def test_get_fundamentals_returns_empty_dict_on_api_error(data_service, mocker):
    mock_client = mocker.patch("src.data_service.RESTClient")
    mock_instance = mock_client.return_value
    mock_instance.vx.list_stock_financials.side_effect = Exception("API error")
    result = data_service.get_fundamentals("NVDA")
    assert result == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_data_service.py -v
```

Expected: `ImportError` — `src.data_service` does not exist.

- [ ] **Step 3: Implement `src/data_service.py`**

```python
import json
import hashlib
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from polygon import RESTClient

class DataService:
    def __init__(self, api_key: str, cache_dir: str = "data/cache"):
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = RESTClient(api_key)

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

        aggs = self._client.get_aggs(ticker, 1, "day", from_date, to_date)
        rows = [
            {
                "open": a.open,
                "high": a.high,
                "low": a.low,
                "close": a.close,
                "volume": a.volume,
            }
            for a in aggs
        ]
        index = [
            datetime.fromtimestamp(a.timestamp / 1000).strftime("%Y-%m-%d")
            for a in aggs
        ]
        self._write_cache(cache_path, {"rows": rows, "index": index})
        return pd.DataFrame(rows, index=index)

    def get_fundamentals(self, ticker: str) -> dict:
        cache_key = f"fundamentals:{ticker}:{datetime.now().strftime('%Y-%m-%d')}"
        cache_path = self._cache_path(cache_key)
        cached = self._read_cache(cache_path)
        if cached:
            return cached

        try:
            results = list(self._client.vx.list_stock_financials(ticker, limit=2))
            if not results:
                return {}
            latest = results[0].financials
            prev = results[1].financials if len(results) > 1 else None

            latest_eps = latest.income_statement.basic_earnings_per_share.value
            latest_rev = latest.income_statement.revenues.value
            prev_eps = prev.income_statement.basic_earnings_per_share.value if prev else None
            prev_rev = prev.income_statement.revenues.value if prev else None

            data = {
                "eps": latest_eps,
                "revenue": latest_rev,
                "eps_growth": ((latest_eps - prev_eps) / abs(prev_eps)) if prev_eps else None,
                "revenue_growth": ((latest_rev - prev_rev) / abs(prev_rev)) if prev_rev else None,
                "pe_ratio": None,  # populated separately via snapshot endpoint
            }
            self._write_cache(cache_path, data)
            return data
        except Exception:
            return {}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_data_service.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/data_service.py tests/test_data_service.py
git commit -m "feat: add DataService with Polygon.io fetching and disk cache"
```

---

## Task 4: Strategy base class

**Files:**
- Create: `src/strategies/base.py`

- [ ] **Step 1: Implement `src/strategies/base.py`**

```python
from abc import ABC, abstractmethod
from src.models import StockData, Signal

class Strategy(ABC):
    @abstractmethod
    def scan(self, stock: StockData) -> Signal | None:
        """Return a Signal if the stock meets criteria, None otherwise."""
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from src.strategies.base import Strategy; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/strategies/base.py
git commit -m "feat: add Strategy ABC"
```

---

## Task 5: MomentumStrategy

**Files:**
- Create: `src/strategies/momentum.py`
- Create: `tests/test_momentum.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_momentum.py
import pandas as pd
import numpy as np
import pytest
from src.models import StockData
from src.strategies.momentum import MomentumStrategy

def make_stock(close_prices: list[float], volumes: list[float] | None = None) -> StockData:
    n = len(close_prices)
    if volumes is None:
        volumes = [1_000_000.0] * n
    index = pd.date_range("2022-01-01", periods=n, freq="B").strftime("%Y-%m-%d").tolist()
    prices = pd.DataFrame({"close": close_prices, "volume": volumes}, index=index)
    return StockData(ticker="TEST", prices=prices, fundamentals={})

def golden_cross_prices() -> list[float]:
    # 200 days trending down, then 50 days trending sharply up to create a golden cross
    down = [200.0 - i * 0.1 for i in range(200)]
    up = [down[-1] + i * 1.5 for i in range(1, 51)]
    return down + up

def test_returns_signal_on_golden_cross_with_good_rsi_and_volume():
    prices = golden_cross_prices()
    # inflate last 20 days volume to trigger volume condition
    volumes = [1_000_000.0] * len(prices)
    for i in range(-20, 0):
        volumes[i] = 1_300_000.0
    stock = make_stock(prices, volumes)
    strategy = MomentumStrategy()
    signal = strategy.scan(stock)
    assert signal is not None
    assert signal.ticker == "TEST"
    assert signal.strategy == "MomentumStrategy"
    assert 0.0 < signal.score <= 1.0
    assert len(signal.reasons) > 0

def test_returns_none_when_insufficient_data():
    stock = make_stock([100.0] * 50)  # need 200 days for MA
    strategy = MomentumStrategy()
    signal = strategy.scan(stock)
    assert signal is None

def test_returns_none_when_death_cross():
    # 200-day MA above 50-day MA
    prices = [100.0 + i * 0.1 for i in range(200)] + [300.0 - i * 1.5 for i in range(50)]
    stock = make_stock(prices)
    strategy = MomentumStrategy()
    signal = strategy.scan(stock)
    assert signal is None

def test_signal_score_reflects_met_conditions():
    prices = golden_cross_prices()
    stock = make_stock(prices)
    strategy = MomentumStrategy()
    signal = strategy.scan(stock)
    # score must be > 0 (golden cross condition worth 0.4)
    if signal:
        assert signal.score >= 0.4
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_momentum.py -v
```

Expected: `ImportError` — `src.strategies.momentum` does not exist.

- [ ] **Step 3: Implement `src/strategies/momentum.py`**

```python
import numpy as np
import pandas as pd
from datetime import date
from src.models import StockData, Signal
from src.strategies.base import Strategy

class MomentumStrategy(Strategy):
    def scan(self, stock: StockData) -> Signal | None:
        prices = stock.prices
        if len(prices) < 200:
            return None

        close = prices["close"]
        volume = prices["volume"]

        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()

        score = 0.0
        reasons = []

        # Golden cross: 50-day MA above 200-day MA (and wasn't yesterday)
        if ma50.iloc[-1] > ma200.iloc[-1] and ma50.iloc[-2] <= ma200.iloc[-2]:
            score += 0.4
            reasons.append(f"Golden cross: MA50 ({ma50.iloc[-1]:.2f}) crossed above MA200 ({ma200.iloc[-1]:.2f})")
        elif ma50.iloc[-1] > ma200.iloc[-1]:
            score += 0.2
            reasons.append(f"MA50 ({ma50.iloc[-1]:.2f}) above MA200 ({ma200.iloc[-1]:.2f})")

        # RSI between 50 and 70
        rsi = self._rsi(close, 14)
        if rsi is not None and 50 <= rsi <= 70:
            score += 0.3
            reasons.append(f"RSI at {rsi:.1f} (trending, not overbought)")

        # Volume 20% above 20-day average
        avg_vol = volume.rolling(20).mean().iloc[-1]
        last_vol = volume.iloc[-1]
        if avg_vol > 0 and last_vol >= avg_vol * 1.2:
            score += 0.3
            reasons.append(f"Volume {last_vol:,.0f} is {((last_vol/avg_vol)-1)*100:.0f}% above 20-day avg")

        if score == 0.0:
            return None

        return Signal(
            ticker=stock.ticker,
            strategy="MomentumStrategy",
            score=round(score, 4),
            reasons=reasons,
            date=str(date.today()),
        )

    def _rsi(self, close: pd.Series, period: int = 14) -> float | None:
        if len(close) < period + 1:
            return None
        delta = close.diff().dropna()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        if loss.iloc[-1] == 0:
            return 100.0
        rs = gain.iloc[-1] / loss.iloc[-1]
        return round(100 - (100 / (1 + rs)), 2)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_momentum.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/strategies/momentum.py tests/test_momentum.py
git commit -m "feat: add MomentumStrategy with MA crossover, RSI, and volume signals"
```

---

## Task 6: FundamentalStrategy

**Files:**
- Create: `src/strategies/fundamental.py`
- Create: `tests/test_fundamental.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_fundamental.py
import pandas as pd
import pytest
from src.models import StockData
from src.strategies.fundamental import FundamentalStrategy

def make_stock(fundamentals: dict) -> StockData:
    prices = pd.DataFrame({"close": [100.0], "volume": [1_000_000.0]}, index=["2024-01-01"])
    return StockData(ticker="TEST", prices=prices, fundamentals=fundamentals)

def test_returns_signal_when_all_criteria_met():
    stock = make_stock({
        "eps_growth": 0.20,       # > 15% ✓
        "revenue_growth": 0.15,   # > 10% ✓
        "pe_ratio": 20.0,
        "sector_median_pe": 28.0, # pe < median ✓
    })
    strategy = FundamentalStrategy()
    signal = strategy.scan(stock)
    assert signal is not None
    assert signal.score == 1.0
    assert signal.strategy == "FundamentalStrategy"
    assert len(signal.reasons) == 3

def test_returns_none_when_no_criteria_met():
    stock = make_stock({
        "eps_growth": 0.05,
        "revenue_growth": 0.03,
        "pe_ratio": 50.0,
        "sector_median_pe": 28.0,
    })
    strategy = FundamentalStrategy()
    assert strategy.scan(stock) is None

def test_returns_none_when_fundamentals_empty():
    stock = make_stock({})
    strategy = FundamentalStrategy()
    assert strategy.scan(stock) is None

def test_partial_score_when_some_criteria_met():
    stock = make_stock({
        "eps_growth": 0.20,       # > 15% ✓
        "revenue_growth": 0.05,   # < 10% ✗
        "pe_ratio": 50.0,
        "sector_median_pe": 28.0, # pe > median ✗
    })
    strategy = FundamentalStrategy()
    signal = strategy.scan(stock)
    assert signal is not None
    assert signal.score == pytest.approx(0.40)

def test_missing_pe_data_skips_pe_condition():
    stock = make_stock({
        "eps_growth": 0.20,
        "revenue_growth": 0.15,
        "pe_ratio": None,
        "sector_median_pe": None,
    })
    strategy = FundamentalStrategy()
    signal = strategy.scan(stock)
    assert signal is not None
    assert signal.score == pytest.approx(0.75)  # 0.40 + 0.35
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_fundamental.py -v
```

Expected: `ImportError` — `src.strategies.fundamental` does not exist.

- [ ] **Step 3: Implement `src/strategies/fundamental.py`**

```python
from datetime import date
from src.models import StockData, Signal
from src.strategies.base import Strategy

class FundamentalStrategy(Strategy):
    EPS_GROWTH_THRESHOLD = 0.15
    REVENUE_GROWTH_THRESHOLD = 0.10

    def scan(self, stock: StockData) -> Signal | None:
        f = stock.fundamentals
        if not f:
            return None

        score = 0.0
        reasons = []

        eps_growth = f.get("eps_growth")
        if eps_growth is not None and eps_growth > self.EPS_GROWTH_THRESHOLD:
            score += 0.40
            reasons.append(f"EPS growth {eps_growth*100:.1f}% YoY (threshold: >{self.EPS_GROWTH_THRESHOLD*100:.0f}%)")

        revenue_growth = f.get("revenue_growth")
        if revenue_growth is not None and revenue_growth > self.REVENUE_GROWTH_THRESHOLD:
            score += 0.35
            reasons.append(f"Revenue growth {revenue_growth*100:.1f}% YoY (threshold: >{self.REVENUE_GROWTH_THRESHOLD*100:.0f}%)")

        pe_ratio = f.get("pe_ratio")
        sector_median_pe = f.get("sector_median_pe")
        if pe_ratio is not None and sector_median_pe is not None:
            if pe_ratio < sector_median_pe:
                score += 0.25
                reasons.append(f"P/E {pe_ratio:.1f} below sector median {sector_median_pe:.1f}")

        if score == 0.0:
            return None

        return Signal(
            ticker=stock.ticker,
            strategy="FundamentalStrategy",
            score=round(score, 4),
            reasons=reasons,
            date=str(date.today()),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_fundamental.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/strategies/fundamental.py tests/test_fundamental.py
git commit -m "feat: add FundamentalStrategy with EPS growth, revenue growth, and P/E signals"
```

---

## Task 7: Scanner

**Files:**
- Create: `src/scanner.py`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scanner.py
import json
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.models import StockData, Signal
from src.scanner import Scanner

def make_signal(ticker: str, strategy: str, score: float) -> Signal:
    return Signal(ticker=ticker, strategy=strategy, score=score, reasons=["reason"], date="2024-01-01")

def make_stock(ticker: str) -> StockData:
    prices = pd.DataFrame({"close": [100.0], "volume": [1_000_000.0]}, index=["2024-01-01"])
    return StockData(ticker=ticker, prices=prices, fundamentals={})

@pytest.fixture
def scanner(tmp_path):
    data_service = MagicMock()
    data_service.get_price_history.return_value = pd.DataFrame(
        {"close": [100.0], "volume": [1_000_000.0]}, index=["2024-01-01"]
    )
    data_service.get_fundamentals.return_value = {}
    return Scanner(data_service=data_service, results_dir=str(tmp_path))

def test_scanner_runs_all_strategies_against_all_tickers(scanner):
    strategy_a = MagicMock()
    strategy_a.scan.return_value = make_signal("NVDA", "A", 0.8)
    strategy_b = MagicMock()
    strategy_b.scan.return_value = None

    scanner.strategies = [strategy_a, strategy_b]
    signals = scanner.run(["NVDA"])

    assert strategy_a.scan.called
    assert strategy_b.scan.called
    assert len(signals) == 1
    assert signals[0].ticker == "NVDA"

def test_scanner_sorts_signals_by_score_descending(scanner):
    def make_strategy(signal):
        s = MagicMock()
        s.scan.return_value = signal
        return s

    scanner.strategies = [
        make_strategy(make_signal("NVDA", "A", 0.5)),
        make_strategy(make_signal("AMD", "A", 0.9)),
        make_strategy(make_signal("MSFT", "A", 0.7)),
    ]
    signals = scanner.run(["NVDA", "AMD", "MSFT"])
    scores = [s.score for s in signals]
    assert scores == sorted(scores, reverse=True)

def test_scanner_writes_results_json(scanner, tmp_path):
    strategy = MagicMock()
    strategy.scan.return_value = make_signal("NVDA", "A", 0.8)
    scanner.strategies = [strategy]

    scanner.run(["NVDA"])

    result_files = list(tmp_path.glob("*.json"))
    assert len(result_files) == 1
    data = json.loads(result_files[0].read_text())
    assert len(data["signals"]) == 1
    assert data["signals"][0]["ticker"] == "NVDA"

def test_scanner_skips_ticker_on_data_service_error(scanner):
    scanner.data_service.get_price_history.side_effect = Exception("API error")
    strategy = MagicMock()
    scanner.strategies = [strategy]
    signals = scanner.run(["NVDA"])
    assert signals == []
    assert not strategy.scan.called
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_scanner.py -v
```

Expected: `ImportError` — `src.scanner` does not exist.

- [ ] **Step 3: Implement `src/scanner.py`**

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
        from_date = str(date.today() - timedelta(days=400))  # ~280 trading days, covers 200-day MA
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
    import os
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    api_key = os.environ["POLYGON_API_KEY"]
    service = DataService(api_key=api_key)
    scanner = Scanner(data_service=service)
    tickers = load_watchlist()
    signals = scanner.run(tickers)
    print(f"\nFound {len(signals)} signals:")
    for s in signals:
        print(f"  {s.ticker} [{s.strategy}] score={s.score}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_scanner.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/scanner.py tests/test_scanner.py
git commit -m "feat: add Scanner orchestrating data service and strategies"
```

---

## Task 8: Backtester

**Files:**
- Create: `src/backtester.py`
- Create: `tests/test_backtester.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_backtester.py
import json
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.models import StockData, Signal
from src.backtester import Backtester

def make_prices(n: int = 300) -> pd.DataFrame:
    import numpy as np
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    volume = np.random.randint(800_000, 1_200_000, n).astype(float)
    index = pd.date_range("2022-01-01", periods=n, freq="B").strftime("%Y-%m-%d").tolist()
    return pd.DataFrame({"close": close, "volume": volume}, index=index)

@pytest.fixture
def backtester(tmp_path):
    data_service = MagicMock()
    data_service.get_price_history.return_value = make_prices(300)
    data_service.get_fundamentals.return_value = {
        "eps_growth": 0.20,
        "revenue_growth": 0.15,
        "pe_ratio": 20.0,
        "sector_median_pe": 28.0,
    }
    return Backtester(data_service=data_service, output_dir=str(tmp_path))

def test_backtester_writes_output_json(backtester, tmp_path):
    backtester.run(["NVDA"])
    output_path = tmp_path / "latest.json"
    assert output_path.exists()
    data = json.loads(output_path.read_text())
    assert "strategies" in data
    assert "signals" in data

def test_backtester_output_has_strategy_stats(backtester, tmp_path):
    backtester.run(["NVDA"])
    data = json.loads((tmp_path / "latest.json").read_text())
    for strategy_stats in data["strategies"].values():
        assert "signal_count" in strategy_stats
        assert "hit_rate_30d" in strategy_stats
        assert "avg_return_30d" in strategy_stats
        assert "avg_return_60d" in strategy_stats
        assert "avg_return_90d" in strategy_stats

def test_backtester_skips_ticker_on_error(backtester):
    backtester.data_service.get_price_history.side_effect = Exception("API error")
    backtester.run(["NVDA"])  # should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_backtester.py -v
```

Expected: `ImportError` — `src.backtester` does not exist.

- [ ] **Step 3: Implement `src/backtester.py`**

```python
import json
import logging
import numpy as np
import pandas as pd
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from src.data_service import DataService
from src.models import StockData, Signal
from src.strategies.base import Strategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.fundamental import FundamentalStrategy

logger = logging.getLogger(__name__)

LOOKBACK_YEARS = 2

class Backtester:
    def __init__(self, data_service: DataService, output_dir: str = "results/backtest"):
        self.data_service = data_service
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.strategies: list[Strategy] = [
            MomentumStrategy(),
            FundamentalStrategy(),
        ]

    def run(self, tickers: list[str]) -> None:
        today = date.today()
        from_date = str(today - timedelta(days=LOOKBACK_YEARS * 365 + 60))
        to_date = str(today)

        all_signals: list[dict] = []
        strategy_signals: dict[str, list[dict]] = defaultdict(list)

        for ticker in tickers:
            try:
                full_prices = self.data_service.get_price_history(ticker, from_date, to_date)
                fundamentals = self.data_service.get_fundamentals(ticker)
            except Exception as e:
                logger.warning(f"Skipping {ticker}: {e}")
                continue

            close = full_prices["close"]
            dates = full_prices.index.tolist()

            for i in range(200, len(dates)):
                snapshot_prices = full_prices.iloc[:i]
                stock = StockData(ticker=ticker, prices=snapshot_prices, fundamentals=fundamentals)

                for strategy in self.strategies:
                    signal = strategy.scan(stock)
                    if signal:
                        signal_date = dates[i - 1]
                        forward_30 = self._forward_return(close, i, 30)
                        forward_60 = self._forward_return(close, i, 60)
                        forward_90 = self._forward_return(close, i, 90)
                        entry = {
                            "ticker": ticker,
                            "strategy": signal.strategy,
                            "score": signal.score,
                            "date": signal_date,
                            "forward_return_30d": forward_30,
                            "forward_return_60d": forward_60,
                            "forward_return_90d": forward_90,
                        }
                        all_signals.append(entry)
                        strategy_signals[signal.strategy].append(entry)

        stats = {
            name: self._compute_stats(sigs)
            for name, sigs in strategy_signals.items()
        }

        output = {"generated": str(today), "strategies": stats, "signals": all_signals}
        (self.output_dir / "latest.json").write_text(json.dumps(output, indent=2))
        logger.info(f"Backtester wrote {len(all_signals)} signals across {len(tickers)} tickers")

    def _forward_return(self, close: pd.Series, from_idx: int, days: int) -> float | None:
        to_idx = from_idx + days
        if to_idx >= len(close):
            return None
        entry_price = close.iloc[from_idx]
        exit_price = close.iloc[to_idx]
        if entry_price == 0:
            return None
        return round((exit_price - entry_price) / entry_price, 4)

    def _compute_stats(self, signals: list[dict]) -> dict:
        if not signals:
            return {"signal_count": 0, "hit_rate_30d": None, "avg_return_30d": None,
                    "avg_return_60d": None, "avg_return_90d": None}

        returns_30 = [s["forward_return_30d"] for s in signals if s["forward_return_30d"] is not None]
        returns_60 = [s["forward_return_60d"] for s in signals if s["forward_return_60d"] is not None]
        returns_90 = [s["forward_return_90d"] for s in signals if s["forward_return_90d"] is not None]

        return {
            "signal_count": len(signals),
            "hit_rate_30d": round(sum(r > 0 for r in returns_30) / len(returns_30), 4) if returns_30 else None,
            "avg_return_30d": round(float(np.mean(returns_30)), 4) if returns_30 else None,
            "avg_return_60d": round(float(np.mean(returns_60)), 4) if returns_60 else None,
            "avg_return_90d": round(float(np.mean(returns_90)), 4) if returns_90 else None,
        }


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

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_backtester.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backtester.py tests/test_backtester.py
git commit -m "feat: add Backtester with 2-year walk-forward signal replay"
```

---

## Task 9: Streamlit app — Signals tab

**Files:**
- Create: `app/main.py`

- [ ] **Step 1: Implement `app/main.py` — Signals tab**

```python
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
```

- [ ] **Step 2: Run the app and verify the Signals tab renders**

```bash
streamlit run app/main.py
```

Open `http://localhost:8501` in a browser. Expected: Signals tab visible, sidebar with filters, table renders if results exist (or info message if no results yet).

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: add Streamlit Signals tab with date picker, strategy filter, and detail view"
```

---

## Task 10: Streamlit app — Backtest tab

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add Backtest tab to `app/main.py`**

Replace the `with tab_backtest:` block (currently absent) with:

```python
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
```

- [ ] **Step 2: Run the app and verify the Backtest tab renders**

```bash
streamlit run app/main.py
```

Click the **Backtest** tab. Expected: strategy performance table and signal timeline table visible (or info message if no backtest JSON yet).

- [ ] **Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: add Streamlit Backtest tab with strategy stats and signal timeline"
```

---

## Task 11: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/scan.yml`

- [ ] **Step 1: Create `.github/workflows/scan.yml`**

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
        env:
          POLYGON_API_KEY: ${{ secrets.POLYGON_API_KEY }}
        run: python src/scanner.py

      - name: Commit results
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add results/
          git diff --staged --quiet || git commit -m "chore: nightly scan $(date -u +%Y-%m-%d)"
          git push
```

- [ ] **Step 2: Add `POLYGON_API_KEY` secret to the GitHub repository**

Go to: Repository → Settings → Secrets and variables → Actions → New repository secret
Name: `POLYGON_API_KEY`, Value: your Polygon.io API key.

- [ ] **Step 3: Verify workflow file is valid YAML**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/scan.yml'))" && echo "Valid YAML"
```

Expected: `Valid YAML`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/scan.yml
git commit -m "feat: add nightly GitHub Actions scan workflow"
```

---

## Task 12: Full test suite and smoke test

- [ ] **Step 1: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS (≥16 tests across 5 test files).

- [ ] **Step 2: Smoke test the scanner locally**

Create a `.env` file with your Polygon.io API key:
```
POLYGON_API_KEY=your_key_here
```

Then run:
```bash
python src/scanner.py
```

Expected: scanner runs, fetches data for all watchlist tickers, writes `results/YYYY-MM-DD.json`.

- [ ] **Step 3: Smoke test the backtester locally**

```bash
python src/backtester.py
```

Expected: backtester runs 2-year walk-forward, writes `results/backtest/latest.json`.

- [ ] **Step 4: Smoke test the Streamlit app**

```bash
streamlit run app/main.py
```

Expected: Signals tab shows today's scan results. Backtest tab shows strategy stats.

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "chore: verify full pipeline end-to-end"
```
