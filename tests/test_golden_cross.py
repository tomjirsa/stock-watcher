import pandas as pd
import pytest
from src.models import StockData
from src.strategies.golden_cross import GoldenCrossStrategy


def make_stock(prices: list[float]) -> StockData:
    index = [str(i) for i in range(len(prices))]
    df = pd.DataFrame({"close": prices, "volume": [1_000_000.0] * len(prices)}, index=index)
    return StockData(ticker="TEST", prices=df, fundamentals={})


# Fresh cross: 200 bars flat at 100, then 1 bar up at 200
# MA50[-1]=102, MA200[-1]=100.5 → cross today
CROSS_TODAY = [100.0] * 200 + [200.0]

# Cross 10 trading days ago: same setup but extended 9 more bars
CROSS_10_DAYS_AGO = [100.0] * 200 + [200.0] * 10

# Cross 21 days ago — outside lookback window
CROSS_21_DAYS_AGO = [100.0] * 200 + [200.0] * 21

# Death cross: falling prices, MA50 below MA200
DEATH_CROSS = [200.0] * 200 + [50.0] * 50


def test_returns_signal_on_fresh_golden_cross():
    strategy = GoldenCrossStrategy()
    signal = strategy.scan(make_stock(CROSS_TODAY))
    assert signal is not None
    assert signal.ticker == "TEST"
    assert signal.strategy == "GoldenCrossStrategy"
    assert signal.score == 1.0


def test_score_is_lower_for_older_cross():
    strategy = GoldenCrossStrategy()
    signal_today = strategy.scan(make_stock(CROSS_TODAY))
    signal_old = strategy.scan(make_stock(CROSS_10_DAYS_AGO))
    assert signal_today is not None
    assert signal_old is not None
    assert signal_today.score > signal_old.score


def test_returns_none_when_cross_outside_lookback_window():
    strategy = GoldenCrossStrategy()
    signal = strategy.scan(make_stock(CROSS_21_DAYS_AGO))
    assert signal is None


def test_returns_none_on_death_cross():
    strategy = GoldenCrossStrategy()
    signal = strategy.scan(make_stock(DEATH_CROSS))
    assert signal is None


def test_returns_none_when_insufficient_data():
    strategy = GoldenCrossStrategy()
    signal = strategy.scan(make_stock([100.0] * 100))
    assert signal is None


def test_reason_mentions_golden_cross():
    strategy = GoldenCrossStrategy()
    signal = strategy.scan(make_stock(CROSS_TODAY))
    assert signal is not None
    assert "Golden cross" in signal.reasons[0]
    assert "MA50" in signal.reasons[0]
    assert "MA200" in signal.reasons[0]
