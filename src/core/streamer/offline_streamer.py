import time
import random
from typing import List, Dict, Any
from datetime import datetime, timedelta
import threading

from .base_streamer import BaseStreamer
from .events import QuoteEvent


class OfflineStreamer(BaseStreamer):
    """
    Offline streamer that generates demo market data for testing purposes.
    Inherits from BaseStreamer and follows the same event-driven pattern.
    """
    
    def __init__(self, symbols: List[str], base_price: float = 18500.0, tick_interval: float = 1.0):
        super().__init__(symbols, name="OfflineStreamer")
        self.base_price = base_price
        self.tick_interval = tick_interval
        self.current_prices = {symbol: base_price for symbol in symbols}
        self.volume_counter = 0
        self._stop_event = threading.Event()
        
    def _setup_connection(self):
        """Setup demo data generation."""
        self._logger.info("Setting up offline demo data generation")
        self._stop_event.clear()
        
        # Initialize symbol mappings for demo
        for symbol in self.symbols:
            self.add_symbol_mapping(symbol, symbol)
    
    def _run_connection(self):
        """Run the demo data generation loop."""
        self._logger.info("Starting demo data generation")
        
        while self._is_running and not self._stop_event.is_set():
            try:
                for symbol in self.symbols:
                    # Generate demo quote data
                    raw_data = self._generate_demo_quote(symbol)
                    
                    # Process through the base class method
                    self._process_raw_quote(raw_data, symbol)
                
                # Wait for next tick
                time.sleep(self.tick_interval)
                
            except Exception as e:
                self._handle_connection_error(e)
                break
    
    def _cleanup_connection(self):
        """Clean up demo connection."""
        self._logger.info("Cleaning up offline streamer")
        self._stop_event.set()
    
    def _normalize_raw_data(self, raw_data: Dict[str, Any], symbol: str) -> QuoteEvent:
        """Normalize demo data to QuoteEvent format."""
        return QuoteEvent(
            symbol=symbol,
            ltp=raw_data['ltp'],
            ltq=raw_data['ltq'],
            ltt=raw_data['ltt'],
            bid=raw_data['bid'],
            ask=raw_data['ask'],
            bid_qty=raw_data['bid_qty'],
            ask_qty=raw_data['ask_qty'],
            volume=raw_data['volume'],
            timestamp=raw_data['timestamp'],
            source=self.name
        )
    
    def _generate_demo_quote(self, symbol: str) -> Dict[str, Any]:
        """Generate realistic demo market data."""
        current_price = self.current_prices[symbol]
        
        # Random walk with mean reversion
        price_change = random.gauss(0, current_price * 0.001)  # 0.1% volatility
        mean_reversion = (self.base_price - current_price) * 0.01  # 1% reversion
        
        new_price = current_price + price_change + mean_reversion
        new_price = max(new_price, self.base_price * 0.95)  # 5% lower bound
        new_price = min(new_price, self.base_price * 1.05)  # 5% upper bound
        
        self.current_prices[symbol] = new_price
        
        # Generate bid/ask spread
        spread_pct = random.uniform(0.0001, 0.001)  # 0.01% to 0.1% spread
        spread = new_price * spread_pct
        
        bid = new_price - spread / 2
        ask = new_price + spread / 2
        
        # Generate volumes
        ltq = random.randint(1, 100)
        bid_qty = random.randint(50, 500)
        ask_qty = random.randint(50, 500)
        
        self.volume_counter += ltq
        
        return {
            'ltp': round(new_price, 2),
            'ltq': ltq,
            'ltt': datetime.now(),
            'bid': round(bid, 2),
            'ask': round(ask, 2),
            'bid_qty': bid_qty,
            'ask_qty': ask_qty,
            'volume': self.volume_counter,
            'timestamp': datetime.now()
        }
    
    def set_base_price(self, price: float):
        """Update base price for demo data."""
        self.base_price = price
        for symbol in self.symbols:
            self.current_prices[symbol] = price
        self._logger.info(f"Updated base price to {price}")
    
    def set_tick_interval(self, interval: float):
        """Update tick generation interval."""
        self.tick_interval = interval
        self._logger.info(f"Updated tick interval to {interval}s")
    
    def get_current_prices(self) -> Dict[str, float]:
        """Get current demo prices."""
        return self.current_prices.copy()
