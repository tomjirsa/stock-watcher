from abc import ABC, abstractmethod
from src.models import StockData, Signal

class Strategy(ABC):
    @abstractmethod
    def scan(self, stock: StockData) -> Signal | None:
        """Return a Signal if the stock meets criteria, None otherwise."""
