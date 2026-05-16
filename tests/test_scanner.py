import json
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.models import StockData, Signal
from src.scanner import Scanner

def make_signal(ticker: str, strategy: str, score: float) -> Signal:
    return Signal(ticker=ticker, strategy=strategy, score=score, reasons=["reason"], date="2024-01-01")

def make_stock(ticker: str) -> StockData:
    prices = pd.DataFrame({"close": [100.0], "volume": [1_000_000.0]}, index=["2024-01-01"])
    return StockData(ticker=ticker, prices=prices, fundamentals={})

@pytest.fixture
def scanner(tmp_path):
    data_service = MagicMock()
    data_service.get_price_history.return_value = pd.DataFrame(
        {"close": [100.0], "volume": [1_000_000.0]}, index=["2024-01-01"]
    )
    data_service.get_fundamentals.return_value = {}
    return Scanner(data_service=data_service, results_dir=str(tmp_path))

def test_scanner_runs_all_strategies_against_all_tickers(scanner):
    strategy_a = MagicMock()
    strategy_a.scan.return_value = make_signal("NVDA", "A", 0.8)
    strategy_b = MagicMock()
    strategy_b.scan.return_value = None

    scanner.strategies = [strategy_a, strategy_b]
    signals = scanner.run(["NVDA"])

    assert strategy_a.scan.called
    assert strategy_b.scan.called
    assert len(signals) == 1
    assert signals[0].ticker == "NVDA"

def test_scanner_sorts_signals_by_score_descending(scanner):
    def make_strategy(signal):
        s = MagicMock()
        s.scan.return_value = signal
        return s

    scanner.strategies = [
        make_strategy(make_signal("NVDA", "A", 0.5)),
        make_strategy(make_signal("AMD", "A", 0.9)),
        make_strategy(make_signal("MSFT", "A", 0.7)),
    ]
    signals = scanner.run(["NVDA", "AMD", "MSFT"])
    scores = [s.score for s in signals]
    assert scores == sorted(scores, reverse=True)

def test_scanner_writes_results_json(scanner, tmp_path):
    strategy = MagicMock()
    strategy.scan.return_value = make_signal("NVDA", "A", 0.8)
    scanner.strategies = [strategy]

    scanner.run(["NVDA"])

    result_files = list(tmp_path.glob("*.json"))
    assert len(result_files) == 1
    data = json.loads(result_files[0].read_text())
    assert len(data["signals"]) == 1
    assert data["signals"][0]["ticker"] == "NVDA"

def test_scanner_skips_ticker_on_data_service_error(scanner):
    scanner.data_service.get_price_history.side_effect = Exception("API error")
    strategy = MagicMock()
    scanner.strategies = [strategy]
    signals = scanner.run(["NVDA"])
    assert signals == []
    assert not strategy.scan.called
