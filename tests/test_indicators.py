import pandas as pd
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

def test_compute_bbands_returns_empty_dataframe_with_insufficient_data():
    result = compute_bbands(make_prices(5))
    assert isinstance(result, pd.DataFrame)
    assert "BBU_20_2.0" in result.columns
    assert len(result) == 0

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

def test_compute_rsi_returns_empty_series_with_insufficient_data():
    result = compute_rsi(make_prices(5))
    assert isinstance(result, pd.Series)
    assert len(result) == 0


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

def test_compute_ema_returns_empty_series_with_insufficient_data():
    result = compute_ema(make_prices(5), length=20)
    assert isinstance(result, pd.Series)
    assert len(result) == 0


def test_compute_ema_returns_series():
    result = compute_ema(make_prices(50), length=20)
    assert isinstance(result, pd.Series)


def test_compute_ema_last_bar_not_nan_with_sufficient_data():
    result = compute_ema(make_prices(50), length=20)
    assert not pd.isna(result.iloc[-1])


def test_compute_ema_tracks_price_direction():
    prices = make_prices(50)  # monotonically increasing
    result = compute_ema(prices, length=20)
    # EMA of an increasing series is itself increasing
    assert result.iloc[-1] > result.iloc[-20]
