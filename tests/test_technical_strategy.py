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
    """RSI below 50 — no signal."""
    return pd.Series([45.0] * n)


def in_range_rsi(n: int) -> pd.Series:
    """RSI between 50 and 70 — signal triggered."""
    return pd.Series([60.0] * n)


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
