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
