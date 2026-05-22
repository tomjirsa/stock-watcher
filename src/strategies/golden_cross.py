import pandas as pd
from datetime import date
from src.models import StockData, Signal
from src.strategies.base import Strategy


class GoldenCrossStrategy(Strategy):
    LOOKBACK_DAYS = 20

    def scan(self, stock: StockData) -> Signal | None:
        prices = stock.prices
        if len(prices) < 201:
            return None

        close = prices["close"]
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()

        # Only look back as far as we have valid MA200 values
        max_lookback = min(self.LOOKBACK_DAYS, len(prices) - 200)
        cross_day = None
        for i in range(1, max_lookback + 1):
            if ma50.iloc[-i] > ma200.iloc[-i] and ma50.iloc[-i - 1] <= ma200.iloc[-i - 1]:
                cross_day = i
                break

        if cross_day is None:
            return None

        score = round(1.0 - (cross_day - 1) * 0.5 / (self.LOOKBACK_DAYS - 1), 4)
        days_ago = cross_day - 1
        label = "today" if days_ago == 0 else f"{days_ago} trading day{'s' if days_ago != 1 else ''} ago"

        return Signal(
            ticker=stock.ticker,
            strategy="GoldenCrossStrategy",
            score=score,
            reasons=[
                f"Golden cross {label}: MA50 ({ma50.iloc[-1]:.2f}) crossed above MA200 ({ma200.iloc[-1]:.2f})"
            ],
            date=str(date.today()),
        )
