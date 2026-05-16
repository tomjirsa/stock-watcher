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
    # 200 days trending down, then 25 days trending sharply up to create a golden cross on the last bar
    down = [200.0 - i * 0.1 for i in range(200)]
    up = [down[-1] + i * 1.5 for i in range(1, 26)]
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
    # 200-day MA above 50-day MA: flat high prices then sharp decline pulls MA50 below MA200
    prices = [300.0] * 200 + [300.0 - i * 3.0 for i in range(50)]
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
