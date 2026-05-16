import numpy as np
import pandas as pd
from datetime import date
from src.models import StockData, Signal
from src.strategies.base import Strategy

class MomentumStrategy(Strategy):
    def scan(self, stock: StockData) -> Signal | None:
        prices = stock.prices
        if len(prices) < 200:
            return None

        close = prices["close"]
        volume = prices["volume"]

        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()

        score = 0.0
        reasons = []

        # Golden cross: 50-day MA above 200-day MA (and wasn't yesterday)
        if ma50.iloc[-1] > ma200.iloc[-1] and ma50.iloc[-2] <= ma200.iloc[-2]:
            score += 0.4
            reasons.append(f"Golden cross: MA50 ({ma50.iloc[-1]:.2f}) crossed above MA200 ({ma200.iloc[-1]:.2f})")
        elif ma50.iloc[-1] > ma200.iloc[-1]:
            score += 0.2
            reasons.append(f"MA50 ({ma50.iloc[-1]:.2f}) above MA200 ({ma200.iloc[-1]:.2f})")

        # RSI between 50 and 70
        rsi = self._rsi(close, 14)
        if rsi is not None and 50 <= rsi <= 70:
            score += 0.3
            reasons.append(f"RSI at {rsi:.1f} (trending, not overbought)")

        # Volume 20% above 20-day average
        avg_vol = volume.rolling(20).mean().iloc[-1]
        last_vol = volume.iloc[-1]
        if avg_vol > 0 and last_vol >= avg_vol * 1.2:
            score += 0.3
            reasons.append(f"Volume {last_vol:,.0f} is {((last_vol/avg_vol)-1)*100:.0f}% above 20-day avg")

        if score == 0.0:
            return None

        return Signal(
            ticker=stock.ticker,
            strategy="MomentumStrategy",
            score=round(score, 4),
            reasons=reasons,
            date=str(date.today()),
        )

    def _rsi(self, close: pd.Series, period: int = 14) -> float | None:
        if len(close) < period + 1:
            return None
        delta = close.diff().dropna()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        if loss.iloc[-1] == 0:
            return 100.0
        rs = gain.iloc[-1] / loss.iloc[-1]
        return round(100 - (100 / (1 + rs)), 2)
