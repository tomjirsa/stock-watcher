import json
import hashlib
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from polygon import RESTClient


class DataService:
    def __init__(self, api_key: str, cache_dir: str = "data/cache"):
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = RESTClient(api_key)

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

        aggs = self._client.get_aggs(ticker, 1, "day", from_date, to_date)
        rows = [
            {
                "open": a.open,
                "high": a.high,
                "low": a.low,
                "close": a.close,
                "volume": a.volume,
            }
            for a in aggs
        ]
        index = [
            datetime.fromtimestamp(a.timestamp / 1000).strftime("%Y-%m-%d")
            for a in aggs
        ]
        self._write_cache(cache_path, {"rows": rows, "index": index})
        return pd.DataFrame(rows, index=index)

    def get_fundamentals(self, ticker: str) -> dict:
        cache_key = f"fundamentals:{ticker}:{datetime.now().strftime('%Y-%m-%d')}"
        cache_path = self._cache_path(cache_key)
        cached = self._read_cache(cache_path)
        if cached:
            return cached

        try:
            results = list(self._client.vx.list_stock_financials(ticker, limit=2))
            if not results:
                return {}
            latest = results[0].financials
            prev = results[1].financials if len(results) > 1 else None

            latest_eps = latest.income_statement.basic_earnings_per_share.value
            latest_rev = latest.income_statement.revenues.value
            prev_eps = prev.income_statement.basic_earnings_per_share.value if prev else None
            prev_rev = prev.income_statement.revenues.value if prev else None

            data = {
                "eps": latest_eps,
                "revenue": latest_rev,
                "eps_growth": ((latest_eps - prev_eps) / abs(prev_eps)) if prev_eps else None,
                "revenue_growth": ((latest_rev - prev_rev) / abs(prev_rev)) if prev_rev else None,
                "pe_ratio": None,  # populated separately via snapshot endpoint
            }
            self._write_cache(cache_path, data)
            return data
        except Exception:
            return {}
