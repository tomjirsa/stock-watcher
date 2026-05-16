import json
import logging
import numpy as np
import pandas as pd
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from src.data_service import DataService
from src.models import StockData, Signal
from src.strategies.base import Strategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.fundamental import FundamentalStrategy

logger = logging.getLogger(__name__)

LOOKBACK_YEARS = 2

class Backtester:
    def __init__(self, data_service: DataService, output_dir: str = "results/backtest"):
        self.data_service = data_service
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.strategies: list[Strategy] = [
            MomentumStrategy(),
            FundamentalStrategy(),
        ]

    def run(self, tickers: list[str]) -> None:
        today = date.today()
        from_date = str(today - timedelta(days=LOOKBACK_YEARS * 365 + 60))
        to_date = str(today)

        all_signals: list[dict] = []
        strategy_signals: dict[str, list[dict]] = defaultdict(list)

        for ticker in tickers:
            try:
                full_prices = self.data_service.get_price_history(ticker, from_date, to_date)
                fundamentals = self.data_service.get_fundamentals(ticker)
            except Exception as e:
                logger.warning(f"Skipping {ticker}: {e}")
                continue

            close = full_prices["close"]
            dates = full_prices.index.tolist()

            for i in range(200, len(dates)):
                snapshot_prices = full_prices.iloc[:i]
                stock = StockData(ticker=ticker, prices=snapshot_prices, fundamentals=fundamentals)

                for strategy in self.strategies:
                    signal = strategy.scan(stock)
                    if signal:
                        signal_date = dates[i - 1]
                        forward_30 = self._forward_return(close, i, 30)
                        forward_60 = self._forward_return(close, i, 60)
                        forward_90 = self._forward_return(close, i, 90)
                        entry = {
                            "ticker": ticker,
                            "strategy": signal.strategy,
                            "score": signal.score,
                            "date": signal_date,
                            "forward_return_30d": forward_30,
                            "forward_return_60d": forward_60,
                            "forward_return_90d": forward_90,
                        }
                        all_signals.append(entry)
                        strategy_signals[signal.strategy].append(entry)

        stats = {
            name: self._compute_stats(sigs)
            for name, sigs in strategy_signals.items()
        }

        output = {"generated": str(today), "strategies": stats, "signals": all_signals}
        (self.output_dir / "latest.json").write_text(json.dumps(output, indent=2))
        logger.info(f"Backtester wrote {len(all_signals)} signals across {len(tickers)} tickers")

    def _forward_return(self, close: pd.Series, from_idx: int, days: int) -> float | None:
        to_idx = from_idx + days
        if to_idx >= len(close):
            return None
        entry_price = close.iloc[from_idx]
        exit_price = close.iloc[to_idx]
        if entry_price == 0:
            return None
        return round((exit_price - entry_price) / entry_price, 4)

    def _compute_stats(self, signals: list[dict]) -> dict:
        if not signals:
            return {"signal_count": 0, "hit_rate_30d": None, "avg_return_30d": None,
                    "avg_return_60d": None, "avg_return_90d": None}

        returns_30 = [s["forward_return_30d"] for s in signals if s["forward_return_30d"] is not None]
        returns_60 = [s["forward_return_60d"] for s in signals if s["forward_return_60d"] is not None]
        returns_90 = [s["forward_return_90d"] for s in signals if s["forward_return_90d"] is not None]

        return {
            "signal_count": len(signals),
            "hit_rate_30d": round(sum(r > 0 for r in returns_30) / len(returns_30), 4) if returns_30 else None,
            "avg_return_30d": round(float(np.mean(returns_30)), 4) if returns_30 else None,
            "avg_return_60d": round(float(np.mean(returns_60)), 4) if returns_60 else None,
            "avg_return_90d": round(float(np.mean(returns_90)), 4) if returns_90 else None,
        }


if __name__ == "__main__":
    import yaml
    logging.basicConfig(level=logging.INFO)

    service = DataService()
    backtester = Backtester(data_service=service)
    with open("config/watchlist.yaml") as f:
        tickers = yaml.safe_load(f)["tickers"]
    backtester.run(tickers)
    print("Backtest complete. Results written to results/backtest/latest.json")
