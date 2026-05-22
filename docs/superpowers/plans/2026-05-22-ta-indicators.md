# Technical Analysis Indicators — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MACD, Bollinger Bands, RSI, and configurable EMA indicators to stock-watcher as both a composite signal strategy and 3-panel Plotly chart overlays on the Signals and Backtest tabs.

**Architecture:** A shared `src/indicators.py` module exposes pure functions (`compute_macd`, `compute_bbands`, `compute_rsi`, `compute_ema`) backed by `pandas-ta`. A new `TechnicalAnalysisStrategy` imports from this module and replaces `MomentumStrategy`. Both Streamlit tabs import the same functions for chart rendering via a shared `build_ta_chart` helper in `app/main.py`.

**Tech Stack:** pandas-ta, Plotly make_subplots, Streamlit, existing yfinance DataService

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Modify | Add `pandas-ta` |
| `src/indicators.py` | **Create** | Pure TA computation functions |
| `src/strategies/technical.py` | **Create** | `TechnicalAnalysisStrategy` — composite scorer |
| `src/strategies/momentum.py` | **Delete** | Superseded by TechnicalAnalysisStrategy |
| `src/scanner.py` | Modify | Swap MomentumStrategy → TechnicalAnalysisStrategy |
| `src/backtester.py` | Modify | Swap MomentumStrategy → TechnicalAnalysisStrategy |
| `app/main.py` | Modify | Add `build_ta_chart`, wire up both tab charts |
| `tests/test_indicators.py` | **Create** | Unit tests for each indicator function |
| `tests/test_technical_strategy.py` | **Create** | Unit tests for TechnicalAnalysisStrategy scoring |
| `tests/test_momentum.py` | **Delete** | Removed with MomentumStrategy |

---

## Task 1: Install pandas-ta and create src/indicators.py

**Files:**
- Modify: `requirements.txt`
- Create: `src/indicators.py`
- Create: `tests/test_indicators.py`

- [ ] **Step 1: Add pandas-ta to requirements.txt**

Open `requirements.txt` and add `pandas-ta==0.3.14b0` after the `numpy` line:

```
yfinance==1.3.0
pandas==2.2.2
numpy==1.26.4
pandas-ta==0.3.14b0
streamlit==1.35.0
plotly==5.22.0
pyyaml==6.0.1
pytest==8.2.0
pytest-mock==3.14.0
```

- [ ] **Step 2: Install the dependency**

```bash
pip install pandas-ta==0.3.14b0
```

Expected: `Successfully installed pandas-ta-0.3.14b0` (or already satisfied).

- [ ] **Step 3: Write failing tests for src/indicators.py**

Create `tests/test_indicators.py`:

```python
import pandas as pd
import pytest
from src.indicators import compute_macd, compute_bbands, compute_rsi, compute_ema


def make_prices(n: int = 100) -> pd.DataFrame:
    close = [100.0 + i * 0.5 for i in range(n)]
    return pd.DataFrame(
        {
            "open":   [p * 0.99 for p in close],
            "high":   [p * 1.01 for p in close],
            "low":    [p * 0.98 for p in close],
            "close":  close,
            "volume": [1_000_000.0] * n,
        },
        index=pd.date_range("2022-01-01", periods=n, freq="B"),
    )


# --- compute_macd ---

def test_compute_macd_returns_dataframe():
    result = compute_macd(make_prices(100))
    assert isinstance(result, pd.DataFrame)


def test_compute_macd_has_required_columns():
    result = compute_macd(make_prices(100))
    assert "MACD_12_26_9" in result.columns
    assert "MACDs_12_26_9" in result.columns
    assert "MACDh_12_26_9" in result.columns


def test_compute_macd_last_bar_not_nan_with_sufficient_data():
    result = compute_macd(make_prices(100))
    assert not pd.isna(result["MACD_12_26_9"].iloc[-1])
    assert not pd.isna(result["MACDs_12_26_9"].iloc[-1])


def test_compute_macd_returns_empty_dataframe_with_insufficient_data():
    result = compute_macd(make_prices(10))
    assert isinstance(result, pd.DataFrame)
    assert "MACD_12_26_9" in result.columns


# --- compute_bbands ---

def test_compute_bbands_returns_dataframe():
    result = compute_bbands(make_prices(50))
    assert isinstance(result, pd.DataFrame)


def test_compute_bbands_has_required_columns():
    result = compute_bbands(make_prices(50))
    assert "BBU_20_2.0" in result.columns
    assert "BBM_20_2.0" in result.columns
    assert "BBL_20_2.0" in result.columns
    assert "BBB_20_2.0" in result.columns


def test_compute_bbands_upper_above_lower():
    result = compute_bbands(make_prices(50))
    assert result["BBU_20_2.0"].iloc[-1] > result["BBL_20_2.0"].iloc[-1]


def test_compute_bbands_mid_between_upper_and_lower():
    result = compute_bbands(make_prices(50))
    assert result["BBL_20_2.0"].iloc[-1] < result["BBM_20_2.0"].iloc[-1] < result["BBU_20_2.0"].iloc[-1]


# --- compute_rsi ---

def test_compute_rsi_returns_series():
    result = compute_rsi(make_prices(50))
    assert isinstance(result, pd.Series)


def test_compute_rsi_last_bar_not_nan_with_sufficient_data():
    result = compute_rsi(make_prices(50))
    assert not pd.isna(result.iloc[-1])


def test_compute_rsi_values_between_0_and_100():
    result = compute_rsi(make_prices(50))
    valid = result.dropna()
    assert (valid >= 0).all() and (valid <= 100).all()


# --- compute_ema ---

def test_compute_ema_returns_series():
    result = compute_ema(make_prices(50), period=20)
    assert isinstance(result, pd.Series)


def test_compute_ema_last_bar_not_nan_with_sufficient_data():
    result = compute_ema(make_prices(50), period=20)
    assert not pd.isna(result.iloc[-1])


def test_compute_ema_tracks_price_direction():
    prices = make_prices(50)  # monotonically increasing
    result = compute_ema(prices, period=20)
    # EMA of an increasing series is itself increasing
    assert result.iloc[-1] > result.iloc[-20]
```

- [ ] **Step 4: Run tests to confirm they fail**

```bash
pytest tests/test_indicators.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.indicators'`

- [ ] **Step 5: Create src/indicators.py**

```python
import pandas as pd
import pandas_ta  # noqa: F401 — registers .ta accessor on DataFrame


def compute_macd(prices: pd.DataFrame) -> pd.DataFrame:
    result = prices.ta.macd(fast=12, slow=26, signal=9)
    if result is None:
        return pd.DataFrame(columns=["MACD_12_26_9", "MACDs_12_26_9", "MACDh_12_26_9"])
    return result


def compute_bbands(prices: pd.DataFrame, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    result = prices.ta.bbands(length=length, std=std)
    if result is None:
        cols = [
            f"BBL_{length}_{std}", f"BBM_{length}_{std}",
            f"BBU_{length}_{std}", f"BBB_{length}_{std}", f"BBP_{length}_{std}",
        ]
        return pd.DataFrame(columns=cols)
    return result


def compute_rsi(prices: pd.DataFrame, length: int = 14) -> pd.Series:
    result = prices.ta.rsi(length=length)
    return result if result is not None else pd.Series(dtype=float)


def compute_ema(prices: pd.DataFrame, period: int) -> pd.Series:
    result = prices.ta.ema(length=period)
    return result if result is not None else pd.Series(dtype=float)
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
pytest tests/test_indicators.py -v
```

Expected: all tests pass (green).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt src/indicators.py tests/test_indicators.py
git commit -m "feat: add src/indicators.py with pandas-ta compute functions"
```

---

## Task 2: Create TechnicalAnalysisStrategy

**Files:**
- Create: `src/strategies/technical.py`
- Create: `tests/test_technical_strategy.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_technical_strategy.py`:

```python
import pandas as pd
import pytest
from unittest.mock import patch
from src.models import StockData
from src.strategies.technical import TechnicalAnalysisStrategy


def make_prices_df(n: int = 50, volume: float = 1_000_000.0) -> pd.DataFrame:
    idx = pd.date_range("2022-01-01", periods=n, freq="B").strftime("%Y-%m-%d").tolist()
    return pd.DataFrame(
        {
            "open":   [99.0] * n,
            "high":   [101.0] * n,
            "low":    [98.0] * n,
            "close":  [100.0] * n,
            "volume": [volume] * n,
        },
        index=idx,
    )


def make_stock(n: int = 50, volume: float = 1_000_000.0) -> StockData:
    return StockData(ticker="TEST", prices=make_prices_df(n, volume), fundamentals={})


def neutral_macd(n: int) -> pd.DataFrame:
    """MACD below signal for all bars — no crossover."""
    return pd.DataFrame(
        {"MACD_12_26_9": [0.1] * n, "MACDs_12_26_9": [0.5] * n, "MACDh_12_26_9": [-0.4] * n}
    )


def crossover_macd(n: int) -> pd.DataFrame:
    """MACD crosses above signal on the last bar."""
    macd = [0.1] * n
    signal = [0.5] * n
    macd[-1] = 0.8   # above signal today
    macd[-2] = 0.3   # below signal yesterday
    return pd.DataFrame(
        {"MACD_12_26_9": macd, "MACDs_12_26_9": signal, "MACDh_12_26_9": [m - s for m, s in zip(macd, signal)]}
    )


def neutral_bbands(n: int) -> pd.DataFrame:
    """Lower band far below price — no conditions triggered."""
    return pd.DataFrame(
        {
            "BBU_20_2.0": [120.0] * n,
            "BBM_20_2.0": [100.0] * n,
            "BBL_20_2.0": [50.0] * n,   # price=100, lower=50 → not within 1%
            "BBB_20_2.0": [70.0] * n,   # high bandwidth, no squeeze
        }
    )


def lower_touch_bbands(n: int) -> pd.DataFrame:
    """Price (100.0) within 1% of lower band."""
    lower = [50.0] * n
    lower[-1] = 99.5  # abs(100 - 99.5) / 99.5 ≈ 0.005 ≤ 0.01
    return pd.DataFrame(
        {"BBU_20_2.0": [120.0] * n, "BBM_20_2.0": [100.0] * n,
         "BBL_20_2.0": lower, "BBB_20_2.0": [70.0] * n}
    )


def squeeze_bbands(n: int) -> pd.DataFrame:
    """Bandwidth at its 126-bar rolling minimum on the last bar."""
    bbb = [20.0] * n
    bbb[-1] = 1.0  # minimum value → rolling min equals current value
    return pd.DataFrame(
        {"BBU_20_2.0": [120.0] * n, "BBM_20_2.0": [100.0] * n,
         "BBL_20_2.0": [50.0] * n, "BBB_20_2.0": bbb}
    )


def neutral_rsi(n: int) -> pd.Series:
    return pd.Series([45.0] * n)  # below 50, no signal


def in_range_rsi(n: int) -> pd.Series:
    return pd.Series([60.0] * n)  # between 50 and 70


# --- insufficient data ---

def test_returns_none_when_fewer_than_26_bars():
    strategy = TechnicalAnalysisStrategy()
    assert strategy.scan(make_stock(n=20)) is None


# --- MACD crossover (+0.30) ---

@patch("src.strategies.technical.compute_bbands")
@patch("src.strategies.technical.compute_rsi")
@patch("src.strategies.technical.compute_macd")
def test_macd_crossover_scores_0_30(mock_macd, mock_rsi, mock_bb):
    n = 50
    mock_macd.return_value = crossover_macd(n)
    mock_rsi.return_value = neutral_rsi(n)
    mock_bb.return_value = neutral_bbands(n)
    stock = make_stock(n)

    signal = TechnicalAnalysisStrategy().scan(stock)

    assert signal is not None
    assert signal.score == pytest.approx(0.30)
    assert any("MACD" in r for r in signal.reasons)


# --- BB lower band touch (+0.20) ---

@patch("src.strategies.technical.compute_bbands")
@patch("src.strategies.technical.compute_rsi")
@patch("src.strategies.technical.compute_macd")
def test_bb_lower_touch_scores_0_20(mock_macd, mock_rsi, mock_bb):
    n = 50
    mock_macd.return_value = neutral_macd(n)
    mock_rsi.return_value = neutral_rsi(n)
    mock_bb.return_value = lower_touch_bbands(n)
    stock = make_stock(n)

    signal = TechnicalAnalysisStrategy().scan(stock)

    assert signal is not None
    assert signal.score == pytest.approx(0.20)
    assert any("Bollinger" in r for r in signal.reasons)


# --- RSI between 50–70 (+0.20) ---

@patch("src.strategies.technical.compute_bbands")
@patch("src.strategies.technical.compute_rsi")
@patch("src.strategies.technical.compute_macd")
def test_rsi_in_range_scores_0_20(mock_macd, mock_rsi, mock_bb):
    n = 50
    mock_macd.return_value = neutral_macd(n)
    mock_rsi.return_value = in_range_rsi(n)
    mock_bb.return_value = neutral_bbands(n)
    stock = make_stock(n)

    signal = TechnicalAnalysisStrategy().scan(stock)

    assert signal is not None
    assert signal.score == pytest.approx(0.20)
    assert any("RSI" in r for r in signal.reasons)


# --- Volume surge (+0.15) ---

@patch("src.strategies.technical.compute_bbands")
@patch("src.strategies.technical.compute_rsi")
@patch("src.strategies.technical.compute_macd")
def test_volume_surge_scores_0_15(mock_macd, mock_rsi, mock_bb):
    n = 50
    mock_macd.return_value = neutral_macd(n)
    mock_rsi.return_value = neutral_rsi(n)
    mock_bb.return_value = neutral_bbands(n)
    # baseline 1_000_000, last bar 1_300_000 = 130% of avg → surge
    volumes = [1_000_000.0] * n
    volumes[-1] = 1_300_000.0
    prices = make_prices_df(n)
    prices["volume"] = volumes
    stock = StockData(ticker="TEST", prices=prices, fundamentals={})

    signal = TechnicalAnalysisStrategy().scan(stock)

    assert signal is not None
    assert signal.score == pytest.approx(0.15)
    assert any("Volume" in r for r in signal.reasons)


# --- BB squeeze (+0.15) ---

@patch("src.strategies.technical.compute_bbands")
@patch("src.strategies.technical.compute_rsi")
@patch("src.strategies.technical.compute_macd")
def test_bb_squeeze_scores_0_15(mock_macd, mock_rsi, mock_bb):
    n = 130  # need ≥126 bars for rolling min
    mock_macd.return_value = neutral_macd(n)
    mock_rsi.return_value = neutral_rsi(n)
    mock_bb.return_value = squeeze_bbands(n)
    stock = make_stock(n)

    signal = TechnicalAnalysisStrategy().scan(stock)

    assert signal is not None
    assert signal.score == pytest.approx(0.15)
    assert any("squeeze" in r.lower() for r in signal.reasons)


# --- No conditions met ---

@patch("src.strategies.technical.compute_bbands")
@patch("src.strategies.technical.compute_rsi")
@patch("src.strategies.technical.compute_macd")
def test_returns_none_when_no_conditions_met(mock_macd, mock_rsi, mock_bb):
    n = 50
    mock_macd.return_value = neutral_macd(n)
    mock_rsi.return_value = neutral_rsi(n)
    mock_bb.return_value = neutral_bbands(n)

    signal = TechnicalAnalysisStrategy().scan(make_stock(n))
    assert signal is None


# --- All conditions met ---

@patch("src.strategies.technical.compute_bbands")
@patch("src.strategies.technical.compute_rsi")
@patch("src.strategies.technical.compute_macd")
def test_all_conditions_score_is_1_0(mock_macd, mock_rsi, mock_bb):
    n = 130
    mock_macd.return_value = crossover_macd(n)
    mock_rsi.return_value = in_range_rsi(n)
    # lower touch + squeeze combined
    bbd = lower_touch_bbands(n)
    bbd["BBB_20_2.0"] = squeeze_bbands(n)["BBB_20_2.0"]
    mock_bb.return_value = bbd

    volumes = [1_000_000.0] * n
    volumes[-1] = 1_300_000.0
    prices = make_prices_df(n)
    prices["volume"] = volumes
    stock = StockData(ticker="TEST", prices=prices, fundamentals={})

    signal = TechnicalAnalysisStrategy().scan(stock)

    assert signal is not None
    assert signal.score == pytest.approx(1.0)
    assert signal.strategy == "TechnicalAnalysisStrategy"
    assert signal.ticker == "TEST"


# --- Signal metadata ---

@patch("src.strategies.technical.compute_bbands")
@patch("src.strategies.technical.compute_rsi")
@patch("src.strategies.technical.compute_macd")
def test_signal_has_correct_strategy_name(mock_macd, mock_rsi, mock_bb):
    n = 50
    mock_macd.return_value = crossover_macd(n)
    mock_rsi.return_value = neutral_rsi(n)
    mock_bb.return_value = neutral_bbands(n)

    signal = TechnicalAnalysisStrategy().scan(make_stock(n))

    assert signal is not None
    assert signal.strategy == "TechnicalAnalysisStrategy"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_technical_strategy.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.strategies.technical'`

- [ ] **Step 3: Create src/strategies/technical.py**

```python
from datetime import date
import pandas as pd
from src.models import StockData, Signal
from src.strategies.base import Strategy
from src.indicators import compute_macd, compute_bbands, compute_rsi


class TechnicalAnalysisStrategy(Strategy):
    MIN_BARS = 26

    def scan(self, stock: StockData) -> Signal | None:
        prices = stock.prices
        if len(prices) < self.MIN_BARS:
            return None

        score = 0.0
        reasons = []

        macd_df = compute_macd(prices)
        bb_df = compute_bbands(prices)
        rsi_s = compute_rsi(prices)

        # MACD bullish crossover (+0.30)
        if "MACD_12_26_9" in macd_df.columns:
            macd_line = macd_df["MACD_12_26_9"]
            signal_line = macd_df["MACDs_12_26_9"]
            if (
                len(macd_line) >= 2
                and not pd.isna(macd_line.iloc[-1])
                and not pd.isna(macd_line.iloc[-2])
                and macd_line.iloc[-1] > signal_line.iloc[-1]
                and macd_line.iloc[-2] <= signal_line.iloc[-2]
            ):
                score += 0.30
                reasons.append(
                    f"MACD bullish crossover: MACD({macd_line.iloc[-1]:.4f})"
                    f" crossed above signal({signal_line.iloc[-1]:.4f})"
                )

        # Price within 1% of lower Bollinger Band (+0.20)
        if "BBL_20_2.0" in bb_df.columns:
            lower = bb_df["BBL_20_2.0"].iloc[-1]
            close = prices["close"].iloc[-1]
            if not pd.isna(lower) and lower > 0 and abs(close - lower) / lower <= 0.01:
                score += 0.20
                reasons.append(
                    f"Price ({close:.2f}) within 1% of lower Bollinger Band ({lower:.2f})"
                )

        # RSI(14) between 50–70 (+0.20)
        if not rsi_s.empty:
            rsi_val = rsi_s.iloc[-1]
            if not pd.isna(rsi_val) and 50 <= rsi_val <= 70:
                score += 0.20
                reasons.append(f"RSI(14) at {rsi_val:.1f} (trending, not overbought)")

        # Volume ≥ 120% of 20-day average (+0.15)
        volume = prices["volume"]
        avg_vol = volume.rolling(20).mean().iloc[-1]
        last_vol = volume.iloc[-1]
        if not pd.isna(avg_vol) and avg_vol > 0 and last_vol >= avg_vol * 1.2:
            score += 0.15
            pct = (last_vol / avg_vol - 1) * 100
            reasons.append(f"Volume ({last_vol:,.0f}) is {pct:.0f}% above 20-day avg")

        # Bollinger Band squeeze — bandwidth at 126-bar rolling minimum (+0.15)
        if "BBB_20_2.0" in bb_df.columns:
            bbb = bb_df["BBB_20_2.0"]
            rolling_min = bbb.rolling(126).min()
            if not pd.isna(rolling_min.iloc[-1]) and bbb.iloc[-1] <= rolling_min.iloc[-1]:
                score += 0.15
                reasons.append(
                    f"Bollinger Band squeeze: bandwidth ({bbb.iloc[-1]:.4f}) at 126-bar low"
                )

        if score == 0.0:
            return None

        return Signal(
            ticker=stock.ticker,
            strategy="TechnicalAnalysisStrategy",
            score=round(score, 4),
            reasons=reasons,
            date=str(date.today()),
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_technical_strategy.py -v
```

Expected: all tests green.

- [ ] **Step 5: Run the full test suite to confirm no regressions**

```bash
pytest -v
```

Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/strategies/technical.py tests/test_technical_strategy.py
git commit -m "feat: add TechnicalAnalysisStrategy with MACD, BBands, RSI, volume scoring"
```

---

## Task 3: Swap strategies in scanner and backtester; delete MomentumStrategy

**Files:**
- Modify: `src/scanner.py`
- Modify: `src/backtester.py`
- Delete: `src/strategies/momentum.py`
- Delete: `tests/test_momentum.py`

- [ ] **Step 1: Update src/scanner.py**

Replace the import and strategy list. The full updated top of `src/scanner.py` (lines 1–24):

```python
import json
import yaml
import logging
from datetime import date, timedelta
from pathlib import Path
from src.data_service import DataService
from src.models import StockData, Signal
from src.strategies.base import Strategy
from src.strategies.technical import TechnicalAnalysisStrategy
from src.strategies.fundamental import FundamentalStrategy
from src.strategies.golden_cross import GoldenCrossStrategy

logger = logging.getLogger(__name__)

class Scanner:
    def __init__(self, data_service: DataService, results_dir: str = "results"):
        self.data_service = data_service
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.strategies: list[Strategy] = [
            TechnicalAnalysisStrategy(),
            FundamentalStrategy(),
            GoldenCrossStrategy(),
        ]
```

- [ ] **Step 2: Update src/backtester.py**

Replace the MomentumStrategy import and usage. Change lines 10 and 32–35:

```python
# Replace this import (line 10):
from src.strategies.momentum import MomentumStrategy
# With:
from src.strategies.technical import TechnicalAnalysisStrategy
```

```python
# Replace the strategies list (lines 32–35):
self.strategies: list[Strategy] = [
    MomentumStrategy(),
    FundamentalStrategy(),
]
# With:
self.strategies: list[Strategy] = [
    TechnicalAnalysisStrategy(),
    FundamentalStrategy(),
]
```

- [ ] **Step 3: Run the test suite to confirm nothing broke**

```bash
pytest -v --ignore=tests/test_momentum.py
```

Expected: all tests pass (test_momentum.py is excluded because MomentumStrategy still exists at this point).

- [ ] **Step 4: Delete momentum.py and test_momentum.py**

```bash
git rm src/strategies/momentum.py tests/test_momentum.py
```

- [ ] **Step 5: Run full suite to confirm clean state**

```bash
pytest -v
```

Expected: all remaining tests pass. `test_momentum.py` no longer exists so it's not collected.

- [ ] **Step 6: Commit**

```bash
git add src/scanner.py src/backtester.py
git commit -m "feat: replace MomentumStrategy with TechnicalAnalysisStrategy in scanner and backtester"
```

---

## Task 4: Add build_ta_chart helper and wire up Signals tab chart

**Files:**
- Modify: `app/main.py`

The Signals tab currently shows score + reasons text when a row is selected. This task adds a 3-panel price chart below it.

- [ ] **Step 1: Add new imports to app/main.py**

At the top of `app/main.py`, replace the existing import block with:

```python
import json
from datetime import date, timedelta
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf
from pathlib import Path
from src.indicators import compute_macd, compute_bbands, compute_rsi, compute_ema
```

- [ ] **Step 2: Add the build_ta_chart function**

Add this function after the `load_price_history` function definition (after line 20, before `RESULTS_DIR = ...`):

```python
def build_ta_chart(prices: pd.DataFrame, ema_period: int = 20) -> go.Figure:
    macd_df = compute_macd(prices)
    bb_df = compute_bbands(prices)
    rsi_s = compute_rsi(prices)
    ema_s = compute_ema(prices, ema_period)

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.6, 0.25, 0.15],
        vertical_spacing=0.03,
    )

    # Row 1 — price line
    fig.add_trace(go.Scatter(
        x=prices.index, y=prices["close"],
        mode="lines", name="Price",
        line=dict(color="#1a73e8", width=1.5),
        hovertemplate="%{x|%Y-%m-%d}: $%{y:.2f}<extra></extra>",
    ), row=1, col=1)

    # Row 1 — Bollinger Bands
    if "BBU_20_2.0" in bb_df.columns:
        for col, label, dash, show in [
            ("BBU_20_2.0", "BB Bands", "dash", True),
            ("BBM_20_2.0", "BB Mid",   "dot",  False),
            ("BBL_20_2.0", "BB Lower", "dash", False),
        ]:
            fig.add_trace(go.Scatter(
                x=prices.index, y=bb_df[col],
                mode="lines", name=label, showlegend=show,
                line=dict(color="#2980b9", width=1, dash=dash),
            ), row=1, col=1)

    # Row 1 — EMA
    if not ema_s.empty:
        fig.add_trace(go.Scatter(
            x=prices.index, y=ema_s,
            mode="lines", name=f"EMA({ema_period})",
            line=dict(color="#e67e22", width=1.5),
        ), row=1, col=1)

    # Row 2 — MACD histogram + lines
    if "MACDh_12_26_9" in macd_df.columns:
        hist = macd_df["MACDh_12_26_9"]
        colors = ["#27ae60" if (not pd.isna(v) and v >= 0) else "#e74c3c" for v in hist]
        fig.add_trace(go.Bar(
            x=prices.index, y=hist,
            name="MACD Hist", marker_color=colors, showlegend=False,
        ), row=2, col=1)
    if "MACD_12_26_9" in macd_df.columns:
        fig.add_trace(go.Scatter(
            x=prices.index, y=macd_df["MACD_12_26_9"],
            mode="lines", name="MACD", line=dict(color="#1a73e8", width=1.5),
        ), row=2, col=1)
    if "MACDs_12_26_9" in macd_df.columns:
        fig.add_trace(go.Scatter(
            x=prices.index, y=macd_df["MACDs_12_26_9"],
            mode="lines", name="Signal", line=dict(color="#e74c3c", width=1.5),
        ), row=2, col=1)

    # Row 3 — RSI
    if not rsi_s.empty:
        fig.add_trace(go.Scatter(
            x=prices.index, y=rsi_s,
            mode="lines", name="RSI(14)", line=dict(color="#8e44ad", width=1.5),
        ), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="#e74c3c", line_width=0.8, row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#27ae60", line_width=0.8, row=3, col=1)

    fig.update_layout(
        template="plotly_white",
        height=520,
        hovermode="x unified",
        showlegend=True,
        xaxis3_title="Date",
        yaxis_title="Price ($)",
        yaxis2_title="MACD",
        yaxis3_title="RSI",
        margin=dict(t=10, b=10),
    )
    return fig
```

- [ ] **Step 3: Update the strategy filter dropdown**

In `app/main.py`, find the sidebar strategy selectbox (the one listing `"GoldenCrossStrategy"`, `"MomentumStrategy"`, `"FundamentalStrategy"`). Replace it with:

```python
        strategy_filter = st.selectbox(
            "Strategy",
            ["All", "TechnicalAnalysisStrategy", "GoldenCrossStrategy", "FundamentalStrategy"],
        )
```

- [ ] **Step 5: Wire up the Signals tab chart**

Find the signal drill-down block in the Signals tab (the block starting `if selected_rows and selected_rows.selection.rows:`). After the existing `for reason in signal["reasons"]: st.write(...)` lines, add:

```python
            st.divider()
            ema_period = st.number_input(
                "EMA period", min_value=5, max_value=200, value=20, step=5, key="signals_ema"
            )
            chart_start = str((date.today() - timedelta(days=400)))
            chart_end = str(date.today())
            with st.spinner(f"Loading {signal['ticker']} chart…"):
                chart_prices = load_price_history(signal["ticker"], chart_start, chart_end)
            if chart_prices.empty:
                st.warning(f"Could not load price history for {signal['ticker']}.")
            else:
                st.plotly_chart(
                    build_ta_chart(chart_prices, int(ema_period)),
                    use_container_width=True,
                )
```

- [ ] **Step 6: Smoke-test the Signals tab**

```bash
streamlit run app/main.py
```

Open the Signals tab, click any signal row. You should see:
- Score metric and reasons text (unchanged)
- A divider
- EMA period number input (default 20)
- 3-panel chart: price + BB + EMA on top, MACD middle, RSI bottom

If no scan results exist yet, run the scanner first:
```bash
python src/scanner.py
```

- [ ] **Step 7: Commit**

```bash
git add app/main.py
git commit -m "feat: add TA chart overlay to Signals tab drill-down"
```

---

## Task 5: Add TA overlays to Backtest tab single-ticker chart

**Files:**
- Modify: `app/main.py`

The Backtest tab single-ticker view (inside `else:` branch after `if bt_ticker_filter == "All":`) currently uses a plain `go.Figure()`. This task replaces it with `build_ta_chart` and adds the buy/sell markers on top.

- [ ] **Step 1: Add the EMA period input above the spinner**

Find the line `with st.spinner(f"Loading {bt_ticker_filter} price history…"):` in the backtest single-ticker block and add the input just before it:

```python
                    ema_period_bt = st.number_input(
                        "EMA period", min_value=5, max_value=200, value=20, step=5, key="backtest_ema"
                    )
                    with st.spinner(f"Loading {bt_ticker_filter} price history…"):
                        prices = load_price_history(bt_ticker_filter, min_date, max_date)
```

- [ ] **Step 2: Replace go.Figure() with build_ta_chart**

Find `fig = go.Figure()` in the single-ticker block and replace it with:

```python
                    fig = build_ta_chart(prices, int(ema_period_bt))
                    fig.update_layout(
                        title=f"{bt_ticker_filter} — Trade History ({horizon} hold)",
                        height=600,
                        hovermode="closest",
                    )
```

Remove the original `fig.update_layout(...)` call at the bottom of the single-ticker block (the one that sets `title`, `xaxis_title`, `yaxis_title`, `hovermode`, `height`).

- [ ] **Step 3: Add row=1, col=1 to all existing fig.add_trace and fig.add_vrect calls**

Every `fig.add_trace(...)` and `fig.add_vrect(...)` in the single-ticker block must specify `row=1, col=1` so they render in the price panel, not on top of MACD or RSI.

Update the price trace (already handled by `build_ta_chart` — remove the original price trace `fig.add_trace(go.Scatter(x=prices.index, y=prices["close"], ...))` since `build_ta_chart` adds it).

Update the shaded hold period vrect:
```python
                        if exit_dt:
                            fig.add_vrect(
                                x0=entry_dt, x1=exit_dt,
                                fillcolor=bar_color, opacity=0.12,
                                layer="below", line_width=0,
                                row=1, col=1,
                            )
```

Update buy marker:
```python
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
                            ), row=1, col=1)
```

Update sell marker:
```python
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
                            ), row=1, col=1)
```

Update legend-only entries:
```python
                    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                        marker=dict(symbol="triangle-up", color="#2ecc71", size=12), name="Buy"),
                        row=1, col=1)
                    fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                        marker=dict(symbol="triangle-down", color="#e74c3c", size=12), name="Sell"),
                        row=1, col=1)
```

- [ ] **Step 4: Remove the now-duplicate original price trace addition**

In the original code there is a block:
```python
                    if not prices.empty:
                        fig.add_trace(go.Scatter(
                            x=prices.index, y=prices["close"],
                            mode="lines", name="Price",
                            line=dict(color="#3498db", width=1.5),
                            hovertemplate="%{x|%Y-%m-%d}: $%{y:.2f}<extra></extra>",
                        ))
```

`build_ta_chart` already adds the price trace, so delete this block entirely.

- [ ] **Step 5: Smoke-test the Backtest tab**

```bash
streamlit run app/main.py
```

Run a backtest first if needed:
```bash
python src/backtester.py
```

Open the Backtest tab, select a single ticker from the "Ticker" dropdown. You should see:
- EMA period number input
- 3-panel chart with price + BB bands + EMA overlay, buy ▲ / sell ▼ markers, shaded hold periods on top panel
- MACD panel in the middle
- RSI panel at the bottom

- [ ] **Step 6: Run the full test suite to confirm no regressions**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/main.py
git commit -m "feat: add TA chart overlays to Backtest tab single-ticker view"
```
