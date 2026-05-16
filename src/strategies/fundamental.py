from datetime import date
from src.models import StockData, Signal
from src.strategies.base import Strategy

class FundamentalStrategy(Strategy):
    EPS_GROWTH_THRESHOLD = 0.15
    REVENUE_GROWTH_THRESHOLD = 0.10

    def scan(self, stock: StockData) -> Signal | None:
        f = stock.fundamentals
        if not f:
            return None

        score = 0.0
        reasons = []

        eps_growth = f.get("eps_growth")
        if eps_growth is not None and eps_growth > self.EPS_GROWTH_THRESHOLD:
            score += 0.40
            reasons.append(f"EPS growth {eps_growth*100:.1f}% YoY (threshold: >{self.EPS_GROWTH_THRESHOLD*100:.0f}%)")

        revenue_growth = f.get("revenue_growth")
        if revenue_growth is not None and revenue_growth > self.REVENUE_GROWTH_THRESHOLD:
            score += 0.35
            reasons.append(f"Revenue growth {revenue_growth*100:.1f}% YoY (threshold: >{self.REVENUE_GROWTH_THRESHOLD*100:.0f}%)")

        pe_ratio = f.get("pe_ratio")
        sector_median_pe = f.get("sector_median_pe")
        if pe_ratio is not None and sector_median_pe is not None:
            if pe_ratio < sector_median_pe:
                score += 0.25
                reasons.append(f"P/E {pe_ratio:.1f} below sector median {sector_median_pe:.1f}")

        if score == 0.0:
            return None

        return Signal(
            ticker=stock.ticker,
            strategy="FundamentalStrategy",
            score=round(score, 4),
            reasons=reasons,
            date=str(date.today()),
        )
