import json
import hashlib
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DataService:
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, key: str) -> Path:
        hashed = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{hashed}.json"

    def _is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age = datetime.now().timestamp() - path.stat().st_mtime
        return age < 86400  # 24 hours

    def _read_cache(self, path: Path) -> dict | None:
        if self._is_fresh(path):
            return json.loads(path.read_text())
        return None

    def _write_cache(self, path: Path, data: dict) -> None:
        path.write_text(json.dumps(data))

    def get_price_history(self, ticker: str, from_date: str, to_date: str) -> pd.DataFrame:
        cache_key = f"prices:{ticker}:{from_date}:{to_date}"
        cache_path = self._cache_path(cache_key)
        cached = self._read_cache(cache_path)
        if cached:
            return pd.DataFrame(cached["rows"], index=cached["index"])

        df = yf.download(ticker, start=from_date, end=to_date, auto_adjust=True, progress=False)
        if df.empty:
            raise ValueError(f"{ticker}: no price data returned")

        # Flatten MultiIndex columns produced by newer yfinance versions
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]]

        index = df.index.strftime("%Y-%m-%d").tolist()
        rows = df.to_dict("records")
        self._write_cache(cache_path, {"rows": rows, "index": index})
        return pd.DataFrame(rows, index=index)

    def get_fundamentals(self, ticker: str) -> dict:
        cache_key = f"fundamentals:{ticker}:{datetime.now().strftime('%Y-%m-%d')}"
        cache_path = self._cache_path(cache_key)
        cached = self._read_cache(cache_path)
        if cached:
            return cached

        try:
            info = yf.Ticker(ticker).info
            data = {
                "eps": info.get("trailingEps"),
                "revenue": info.get("totalRevenue"),
                "eps_growth": info.get("earningsGrowth"),
                "revenue_growth": info.get("revenueGrowth"),
                "pe_ratio": info.get("trailingPE"),
                "sector_median_pe": None,
            }
            self._write_cache(cache_path, data)
            return data
        except Exception as e:
            logger.warning(f"Failed to fetch fundamentals for {ticker}: {e}")
            return {}
