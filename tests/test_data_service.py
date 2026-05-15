import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from src.data_service import DataService

@pytest.fixture
def data_service(tmp_path):
    with patch("src.data_service.RESTClient"):
        return DataService(api_key="test_key", cache_dir=str(tmp_path))

def test_get_price_history_returns_dataframe(data_service, mocker):
    mock_client = mocker.patch("src.data_service.RESTClient")
    mock_instance = mock_client.return_value
    mock_instance.get_aggs.return_value = [
        MagicMock(timestamp=1704067200000, open=100.0, high=105.0, low=99.0, close=103.0, volume=1000000),
        MagicMock(timestamp=1704153600000, open=103.0, high=108.0, low=102.0, close=106.0, volume=1200000),
    ]
    data_service._client = mock_instance
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
    data_service._client = mock_instance
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
    data_service._client = mock_instance
    result = data_service.get_fundamentals("NVDA")
    assert isinstance(result, dict)
    assert "eps" in result
    assert "revenue" in result

def test_get_fundamentals_returns_empty_dict_on_api_error(data_service, mocker):
    mock_client = mocker.patch("src.data_service.RESTClient")
    mock_instance = mock_client.return_value
    mock_instance.vx.list_stock_financials.side_effect = Exception("API error")
    data_service._client = mock_instance
    result = data_service.get_fundamentals("NVDA")
    assert result == {}
