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
