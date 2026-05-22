import pandas as pd
import pandas_ta  # noqa: F401 — registers .ta accessor on DataFrame


def compute_macd(prices: pd.DataFrame) -> pd.DataFrame:
    _empty = pd.DataFrame(columns=["MACD_12_26_9", "MACDs_12_26_9", "MACDh_12_26_9"])
    result = prices.ta.macd(fast=12, slow=26, signal=9)
    if result is None:
        return _empty
    # pandas-ta >= 0.4 may return the original prices frame when data is insufficient
    if "MACD_12_26_9" not in result.columns:
        return _empty
    return result


def compute_bbands(prices: pd.DataFrame, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    _empty_cols = [
        f"BBL_{length}_{std}", f"BBM_{length}_{std}",
        f"BBU_{length}_{std}", f"BBB_{length}_{std}", f"BBP_{length}_{std}",
    ]
    result = prices.ta.bbands(length=length, std=std)
    # pandas-ta >= 0.4 returns the original prices frame when data is insufficient
    if not isinstance(result, pd.DataFrame) or f"BBU_{length}_{std}_{std}" not in result.columns:
        if isinstance(result, pd.DataFrame) and f"BBU_{length}_{std}" in result.columns:
            return result  # already canonical (future version that fixes naming)
        return pd.DataFrame(columns=_empty_cols)
    # pandas-ta 0.4.x appends a duplicate std suffix — normalise to canonical names.
    double_suffix = f"_{std}_{std}"
    canonical_suffix = f"_{std}"
    rename_map = {
        col: col.replace(double_suffix, canonical_suffix, 1)
        for col in result.columns
        if col.endswith(double_suffix)
    }
    return result.rename(columns=rename_map) if rename_map else result


def compute_rsi(prices: pd.DataFrame, length: int = 14) -> pd.Series:
    result = prices.ta.rsi(length=length)
    # pandas-ta >= 0.4 returns the original prices frame when data is insufficient
    return result if isinstance(result, pd.Series) else pd.Series(dtype=float)


def compute_ema(prices: pd.DataFrame, length: int) -> pd.Series:
    result = prices.ta.ema(length=length)
    # pandas-ta >= 0.4 returns the original prices frame when data is insufficient
    return result if isinstance(result, pd.Series) else pd.Series(dtype=float)
