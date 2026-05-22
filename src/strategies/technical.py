from datetime import date
import pandas as pd
from src.models import StockData, Signal
from src.strategies.base import Strategy
from src.indicators import compute_macd, compute_bbands, compute_rsi


class TechnicalAnalysisStrategy(Strategy):
    MIN_BARS = 26

    def scan(self, stock: StockData) -> Signal | None:
        prices = stock.prices
        if len(prices) < self.MIN_BARS:
            return None

        score = 0.0
        reasons = []

        macd_df = compute_macd(prices)
        bb_df = compute_bbands(prices)
        rsi_s = compute_rsi(prices)

        # MACD bullish crossover (+0.30)
        if "MACD_12_26_9" in macd_df.columns:
            macd_line = macd_df["MACD_12_26_9"]
            signal_line = macd_df["MACDs_12_26_9"]
            if (
                len(macd_line) >= 2
                and not pd.isna(macd_line.iloc[-1])
                and not pd.isna(macd_line.iloc[-2])
                and macd_line.iloc[-1] > signal_line.iloc[-1]
                and macd_line.iloc[-2] <= signal_line.iloc[-2]
            ):
                score += 0.30
                reasons.append(
                    f"MACD bullish crossover: MACD({macd_line.iloc[-1]:.4f})"
                    f" crossed above signal({signal_line.iloc[-1]:.4f})"
                )

        # Price within 1% of lower Bollinger Band (+0.20)
        if "BBL_20_2.0" in bb_df.columns:
            lower = bb_df["BBL_20_2.0"].iloc[-1]
            close = prices["close"].iloc[-1]
            if not pd.isna(lower) and lower > 0 and abs(close - lower) / lower <= 0.01:
                score += 0.20
                reasons.append(
                    f"Price ({close:.2f}) within 1% of lower Bollinger Band ({lower:.2f})"
                )

        # RSI(14) between 50–70 (+0.20)
        if not rsi_s.empty:
            rsi_val = rsi_s.iloc[-1]
            if not pd.isna(rsi_val) and 50 <= rsi_val <= 70:
                score += 0.20
                reasons.append(f"RSI(14) at {rsi_val:.1f} (trending, not overbought)")

        # Volume ≥ 120% of 20-day average (+0.15)
        volume = prices["volume"]
        avg_vol = volume.rolling(20).mean().iloc[-1]
        last_vol = volume.iloc[-1]
        if not pd.isna(avg_vol) and avg_vol > 0 and last_vol >= avg_vol * 1.2:
            score += 0.15
            pct = (last_vol / avg_vol - 1) * 100
            reasons.append(f"Volume ({last_vol:,.0f}) is {pct:.0f}% above 20-day avg")

        # Bollinger Band squeeze — bandwidth at 126-bar rolling minimum (+0.15)
        if "BBB_20_2.0" in bb_df.columns:
            bbb = bb_df["BBB_20_2.0"]
            rolling_min = bbb.rolling(126).min()
            if not pd.isna(rolling_min.iloc[-1]) and bbb.iloc[-1] <= rolling_min.iloc[-1]:
                score += 0.15
                reasons.append(
                    f"Bollinger Band squeeze: bandwidth ({bbb.iloc[-1]:.4f}) at 126-bar low"
                )

        if score == 0.0:
            return None

        return Signal(
            ticker=stock.ticker,
            strategy="TechnicalAnalysisStrategy",
            score=round(score, 4),
            reasons=reasons,
            date=str(date.today()),
        )
