from dataclasses import dataclass, field
import pandas as pd

@dataclass
class StockData:
    ticker: str
    prices: pd.DataFrame
    fundamentals: dict

@dataclass
class Signal:
    ticker: str
    strategy: str
    score: float
    reasons: list[str]
    date: str
