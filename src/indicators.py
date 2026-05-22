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
    result = prices.ta.bbands(length=length, std=std)
    if result is None:
        cols = [
            f"BBL_{length}_{std}", f"BBM_{length}_{std}",
            f"BBU_{length}_{std}", f"BBB_{length}_{std}", f"BBP_{length}_{std}",
        ]
        return pd.DataFrame(columns=cols)
    # pandas-ta 0.4.x names columns as BBL_{length}_{std}_{std} — normalise to
    # BBL_{length}_{std} so downstream code uses a single canonical name.
    rename_map = {}
    for col in result.columns:
        for prefix in ("BBL", "BBM", "BBU", "BBB", "BBP"):
            suffix = f"_{length}_{std}_{std}"
            if col == f"{prefix}{suffix}":
                rename_map[col] = f"{prefix}_{length}_{std}"
    if rename_map:
        result = result.rename(columns=rename_map)
    return result


def compute_rsi(prices: pd.DataFrame, length: int = 14) -> pd.Series:
    result = prices.ta.rsi(length=length)
    return result if result is not None else pd.Series(dtype=float)


def compute_ema(prices: pd.DataFrame, period: int) -> pd.Series:
    result = prices.ta.ema(length=period)
    return result if result is not None else pd.Series(dtype=float)
