import json
import yaml
import logging
from datetime import date, timedelta
from pathlib import Path
from src.data_service import DataService
from src.models import StockData, Signal
from src.strategies.base import Strategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.fundamental import FundamentalStrategy
from src.strategies.golden_cross import GoldenCrossStrategy

logger = logging.getLogger(__name__)

class Scanner:
    def __init__(self, data_service: DataService, results_dir: str = "results"):
        self.data_service = data_service
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.strategies: list[Strategy] = [
            MomentumStrategy(),
            FundamentalStrategy(),
            GoldenCrossStrategy(),
        ]

    def run(self, tickers: list[str]) -> list[Signal]:
        today = str(date.today())
        from_date = str(date.today() - timedelta(days=400))
        signals = []

        for ticker in tickers:
            try:
                prices = self.data_service.get_price_history(ticker, from_date, today)
                fundamentals = self.data_service.get_fundamentals(ticker)
                stock = StockData(ticker=ticker, prices=prices, fundamentals=fundamentals)
            except Exception as e:
                logger.warning(f"Skipping {ticker}: {e}")
                continue

            for strategy in self.strategies:
                signal = strategy.scan(stock)
                if signal:
                    signals.append(signal)

        signals.sort(key=lambda s: s.score, reverse=True)
        self._write_results(signals, today)
        return signals

    def _write_results(self, signals: list[Signal], today: str) -> None:
        output = {
            "date": today,
            "signals": [
                {
                    "ticker": s.ticker,
                    "strategy": s.strategy,
                    "score": s.score,
                    "reasons": s.reasons,
                    "date": s.date,
                }
                for s in signals
            ],
        }
        path = self.results_dir / f"{today}.json"
        path.write_text(json.dumps(output, indent=2))
        logger.info(f"Wrote {len(signals)} signals to {path}")


def load_watchlist(path: str = "config/watchlist.yaml") -> list[str]:
    with open(path) as f:
        return yaml.safe_load(f)["tickers"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    service = DataService()
    scanner = Scanner(data_service=service)
    tickers = load_watchlist()
    signals = scanner.run(tickers)
    print(f"\nFound {len(signals)} signals:")
    for s in signals:
        print(f"  {s.ticker} [{s.strategy}] score={s.score}")
