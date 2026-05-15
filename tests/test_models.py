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
