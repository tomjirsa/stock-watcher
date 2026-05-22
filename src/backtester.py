import json
import logging
import numpy as np
import pandas as pd
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from src.data_service import DataService
from src.models import StockData, Signal
from src.strategies.base import Strategy
from src.strategies.technical import TechnicalAnalysisStrategy
from src.strategies.fundamental import FundamentalStrategy

logger = logging.getLogger(__name__)

LOOKBACK_YEARS = 2


class Backtester:
    def __init__(
        self,
        data_service: DataService,
        output_dir: str = "results/backtest",
        hold_days: int = 90,
        investment_per_trade: float = 1000.0,
    ):
        self.data_service = data_service
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.hold_days = hold_days
        self.investment_per_trade = investment_per_trade
        self.strategies: list[Strategy] = [
            TechnicalAnalysisStrategy(),
            FundamentalStrategy(),
        ]

    def run(self, tickers: list[str]) -> None:
        today = date.today()
        from_date = str(today - timedelta(days=LOOKBACK_YEARS * 365 + 60))
        to_date = str(today)

        all_trades: list[dict] = []
        strategy_trades: dict[str, list[dict]] = defaultdict(list)

        for ticker in tickers:
            try:
                full_prices = self.data_service.get_price_history(ticker, from_date, to_date)
                fundamentals = self.data_service.get_fundamentals(ticker)
            except Exception as e:
                logger.warning(f"Skipping {ticker}: {e}")
                continue

            close = full_prices["close"]
            dates = full_prices.index.tolist()
            last_entry: dict[str, date] = {}  # strategy -> last entry date

            for i in range(200, len(dates)):
                snapshot_prices = full_prices.iloc[:i]
                stock = StockData(ticker=ticker, prices=snapshot_prices, fundamentals=fundamentals)
                signal_date_str = dates[i - 1]
                signal_date = datetime.strptime(signal_date_str, "%Y-%m-%d").date()

                for strategy in self.strategies:
                    signal = strategy.scan(stock)
                    if not signal:
                        continue

                    strat_name = signal.strategy
                    prev = last_entry.get(strat_name)
                    if prev is not None and (signal_date - prev).days < self.hold_days:
                        continue  # still within hold period

                    last_entry[strat_name] = signal_date
                    forward_30 = self._forward_return(close, i, 30)
                    forward_60 = self._forward_return(close, i, 60)
                    forward_90 = self._forward_return(close, i, 90)

                    trade = {
                        "ticker": ticker,
                        "strategy": strat_name,
                        "score": signal.score,
                        "entry_date": signal_date_str,
                        "exit_date_30d": self._offset_date(signal_date_str, 30),
                        "exit_date_60d": self._offset_date(signal_date_str, 60),
                        "exit_date_90d": self._offset_date(signal_date_str, 90),
                        "forward_return_30d": forward_30,
                        "forward_return_60d": forward_60,
                        "forward_return_90d": forward_90,
                    }
                    all_trades.append(trade)
                    strategy_trades[strat_name].append(trade)

        stats = {
            name: self._compute_stats(trades)
            for name, trades in strategy_trades.items()
        }

        output = {
            "generated": str(today),
            "config": {
                "hold_days": self.hold_days,
                "investment_per_trade": self.investment_per_trade,
            },
            "strategies": stats,
            "trades": all_trades,
        }
        (self.output_dir / "latest.json").write_text(json.dumps(output, indent=2))
        logger.info(f"Backtester wrote {len(all_trades)} trades across {len(tickers)} tickers")

    def _offset_date(self, date_str: str, days: int) -> str:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        return str(d + timedelta(days=days))

    def _forward_return(self, close: pd.Series, from_idx: int, days: int) -> float | None:
        to_idx = from_idx + days
        if to_idx >= len(close):
            return None
        entry_price = close.iloc[from_idx]
        exit_price = close.iloc[to_idx]
        if entry_price == 0:
            return None
        return round((exit_price - entry_price) / entry_price, 4)

    def _compute_stats(self, trades: list[dict]) -> dict:
        if not trades:
            return {
                "trade_count": 0,
                "win_rate_30d": None, "win_rate_60d": None, "win_rate_90d": None,
                "avg_return_30d": None, "avg_return_60d": None, "avg_return_90d": None,
            }

        r30 = [t["forward_return_30d"] for t in trades if t["forward_return_30d"] is not None]
        r60 = [t["forward_return_60d"] for t in trades if t["forward_return_60d"] is not None]
        r90 = [t["forward_return_90d"] for t in trades if t["forward_return_90d"] is not None]

        return {
            "trade_count": len(trades),
            "win_rate_30d": round(sum(r > 0 for r in r30) / len(r30), 4) if r30 else None,
            "win_rate_60d": round(sum(r > 0 for r in r60) / len(r60), 4) if r60 else None,
            "win_rate_90d": round(sum(r > 0 for r in r90) / len(r90), 4) if r90 else None,
            "avg_return_30d": round(float(np.mean(r30)), 4) if r30 else None,
            "avg_return_60d": round(float(np.mean(r60)), 4) if r60 else None,
            "avg_return_90d": round(float(np.mean(r90)), 4) if r90 else None,
        }


if __name__ == "__main__":
    import yaml
    logging.basicConfig(level=logging.INFO)

    config = {}
    try:
        with open("config/backtest.yaml") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        pass

    service = DataService()
    backtester = Backtester(
        data_service=service,
        hold_days=config.get("hold_days", 90),
        investment_per_trade=config.get("investment_per_trade", 1000.0),
    )
    with open("config/watchlist.yaml") as f:
        tickers = yaml.safe_load(f)["tickers"]
    backtester.run(tickers)
    print("Backtest complete. Results written to results/backtest/latest.json")
