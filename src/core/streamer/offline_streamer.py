import random
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.core.event_bus.events import QuoteEvent
from .base_streamer import BaseStreamer


class OfflineStreamer(BaseStreamer):
    """Generates synthetic random-walk market data for offline testing."""

    def __init__(self, symbols: List[str], base_price: float = 18500.0, tick_interval: float = 1.0):
        super().__init__(symbols, name="OfflineStreamer")
        self.base_price = base_price
        self.tick_interval = tick_interval
        self._current_prices = {s: base_price for s in symbols}
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # BaseStreamer interface
    # ------------------------------------------------------------------

    def _setup_connection(self):
        self._stop_event.clear()
        self._logger.info("Offline streamer ready")

    def _run_connection(self):
        self._logger.info("Offline data generation started")
        while self._is_running and not self._stop_event.is_set():
            for symbol in self.symbols:
                raw = self._generate_tick(symbol)
                event = self._normalize_raw_data(raw, symbol)
                if event:
                    self.publish_quote(event)
            # Interruptible sleep — wakes immediately on stop()
            self._stop_event.wait(timeout=self.tick_interval)

    def _cleanup_connection(self):
        self._stop_event.set()

    def _normalize_raw_data(self, raw_data: Dict[str, Any], symbol: str) -> Optional[QuoteEvent]:
        return QuoteEvent(
            timestamp=raw_data['timestamp'],
            source=self.name,
            instrument=symbol,
            name=symbol,
            ltp=raw_data['ltp'],
            ltq=float(raw_data['volume']),
        )

    # ------------------------------------------------------------------
    # Price generation
    # ------------------------------------------------------------------

    def _generate_tick(self, symbol: str) -> Dict[str, Any]:
        price = self._current_prices[symbol]
        change = random.gauss(0, price * 0.001)
        revert = (self.base_price - price) * 0.01
        price = price + change + revert
        price = max(self.base_price * 0.95, min(price, self.base_price * 1.05))
        self._current_prices[symbol] = price
        return {
            'ltp': round(price, 2),
            'volume': random.randint(1, 100),
            'timestamp': datetime.now(),
        }

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------

    def set_base_price(self, price: float):
        self.base_price = price
        for s in self.symbols:
            self._current_prices[s] = price
        self._logger.info(f"Base price set to {price}")

    def set_tick_interval(self, interval: float):
        self.tick_interval = interval

    def get_current_prices(self) -> Dict[str, float]:
        return dict(self._current_prices)
