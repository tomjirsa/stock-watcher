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
from src.strategies.golden_cross import GoldenCrossStrategy

logger = logging.getLogger(__name__)

LOOKBACK_YEARS = 2

STRATEGY_WEIGHTS: dict[str, float] = {
    "TechnicalAnalysisStrategy": 0.50,
    "FundamentalStrategy": 0.30,
    "GoldenCrossStrategy": 0.20,
}
COMBINED_THRESHOLD = 0.50


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
            GoldenCrossStrategy(),
        ]

    def run(self, tickers: list[str]) -> None:
        today = date.today()
        from_date = str(today - timedelta(days=LOOKBACK_YEARS * 365 + 60))
        to_date = str(today)

        all_trades: list[dict] = []

        for ticker in tickers:
            try:
                full_prices = self.data_service.get_price_history(ticker, from_date, to_date)
                fundamentals = self.data_service.get_fundamentals(ticker)
            except Exception as e:
                logger.warning(f"Skipping {ticker}: {e}")
                continue

            close = full_prices["close"]
            dates = full_prices.index.tolist()
            last_entry: date | None = None

            for i in range(200, len(dates)):
                signal_date_str = dates[i - 1]
                signal_date = datetime.strptime(signal_date_str, "%Y-%m-%d").date()

                if last_entry is not None and (signal_date - last_entry).days < self.hold_days:
                    continue

                snapshot_prices = full_prices.iloc[:i]
                stock = StockData(ticker=ticker, prices=snapshot_prices, fundamentals=fundamentals)

                fired: dict[str, Signal] = {}
                for strategy in self.strategies:
                    sig = strategy.scan(stock)
                    if sig:
                        fired[sig.strategy] = sig

                combined_score = sum(
                    sig.score * STRATEGY_WEIGHTS.get(name, 0.0)
                    for name, sig in fired.items()
                )

                if combined_score < COMBINED_THRESHOLD:
                    continue

                last_entry = signal_date
                all_reasons = [r for sig in fired.values() for r in sig.reasons]

                trade = {
                    "ticker": ticker,
                    "strategy": "CombinedSignal",
                    "strategies_fired": sorted(fired.keys()),
                    "score": round(combined_score, 4),
                    "reasons": all_reasons,
                    "entry_date": signal_date_str,
                    "exit_date_30d": self._offset_date(signal_date_str, 30),
                    "exit_date_60d": self._offset_date(signal_date_str, 60),
                    "exit_date_90d": self._offset_date(signal_date_str, 90),
                    "forward_return_30d": self._forward_return(close, i, 30),
                    "forward_return_60d": self._forward_return(close, i, 60),
                    "forward_return_90d": self._forward_return(close, i, 90),
                }
                all_trades.append(trade)

        combined_trades = [t for t in all_trades if t["strategy"] == "CombinedSignal"]
        stats = {"CombinedSignal": self._compute_stats(combined_trades)}

        output = {
            "generated": str(today),
            "config": {
                "hold_days": self.hold_days,
                "investment_per_trade": self.investment_per_trade,
                "weights": STRATEGY_WEIGHTS,
                "threshold": COMBINED_THRESHOLD,
            },
            "strategies": stats,
            "trades": all_trades,
        }
        payload = json.dumps(output, indent=2)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        run_path = self.output_dir / f"{timestamp}.json"
        run_path.write_text(payload)
        (self.output_dir / "latest.json").write_text(payload)
        logger.info(f"Backtester wrote {len(all_trades)} trades to {run_path.name}")

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
