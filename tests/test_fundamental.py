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
