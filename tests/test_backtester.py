import json
import pandas as pd
import pytest
from unittest.mock import MagicMock
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
    return Backtester(data_service=data_service, output_dir=str(tmp_path), hold_days=90, investment_per_trade=1000.0)


def test_backtester_writes_output_json(backtester, tmp_path):
    backtester.run(["NVDA"])
    output_path = tmp_path / "latest.json"
    assert output_path.exists()
    data = json.loads(output_path.read_text())
    assert "strategies" in data
    assert "trades" in data
    assert "config" in data


def test_backtester_output_has_strategy_stats(backtester, tmp_path):
    backtester.run(["NVDA"])
    data = json.loads((tmp_path / "latest.json").read_text())
    for stats in data["strategies"].values():
        assert "trade_count" in stats
        assert "win_rate_30d" in stats
        assert "win_rate_60d" in stats
        assert "win_rate_90d" in stats
        assert "avg_return_30d" in stats
        assert "avg_return_60d" in stats
        assert "avg_return_90d" in stats


def test_backtester_output_has_config(backtester, tmp_path):
    backtester.run(["NVDA"])
    data = json.loads((tmp_path / "latest.json").read_text())
    assert data["config"]["hold_days"] == 90
    assert data["config"]["investment_per_trade"] == 1000.0


def test_backtester_deduplicates_signals(tmp_path):
    data_service = MagicMock()
    data_service.get_price_history.return_value = make_prices(300)
    data_service.get_fundamentals.return_value = {
        "eps_growth": 0.20,
        "revenue_growth": 0.15,
    }
    bt = Backtester(data_service=data_service, output_dir=str(tmp_path), hold_days=90)
    bt.run(["NVDA"])
    data = json.loads((tmp_path / "latest.json").read_text())

    for strat_name in data["strategies"]:
        trades = [t for t in data["trades"] if t["strategy"] == strat_name]
        for i in range(1, len(trades)):
            from datetime import datetime
            prev = datetime.strptime(trades[i - 1]["entry_date"], "%Y-%m-%d").date()
            curr = datetime.strptime(trades[i]["entry_date"], "%Y-%m-%d").date()
            assert (curr - prev).days >= 90, (
                f"{strat_name}: re-entry after only {(curr - prev).days} days"
            )


def test_backtester_skips_ticker_on_error(backtester):
    backtester.data_service.get_price_history.side_effect = Exception("API error")
    backtester.run(["NVDA"])  # should not raise
