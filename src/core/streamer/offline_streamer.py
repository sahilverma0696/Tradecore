import time
import random
from typing import List, Dict, Any
from datetime import datetime
import threading

from .base_streamer import BaseStreamer


class OfflineStreamer(BaseStreamer):
    """
    Offline streamer that generates demo market data for testing purposes.
    Uses the simplified BaseStreamer interface.
    """
    
    def __init__(self, symbols: List[str], base_price: float = 1337.0, tick_interval: float = 1.0):
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
    
    def _run_connection(self):
        """Run the demo data generation loop."""
        self._logger.info("Starting demo data generation")
        
        while self._is_running and not self._stop_event.is_set():
            try:
                for symbol in self.symbols:
                    # Generate demo quote data
                    quote_data = self._generate_demo_quote(symbol)
                    
                    # Use base class publish_quote method
                    self.publish_quote(
                        symbol=symbol,
                        ltp=quote_data['ltp'],
                        volume=quote_data['volume'],
                        bid=quote_data['bid'],
                        ask=quote_data['ask'],
                        raw_data=quote_data
                    )
                
                # Wait for next tick
                time.sleep(self.tick_interval)
                
            except Exception as e:
                self._logger.error(f"Error in demo data generation: {e}")
                break
    
    def _cleanup_connection(self):
        """Clean up demo connection."""
        self._logger.info("Cleaning up offline streamer")
        self._stop_event.set()
    
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
        
        # Generate volume
        volume = random.randint(1, 100)
        self.volume_counter += volume
        
        return {
            'ltp': round(new_price, 2),
            'bid': round(bid, 2),
            'ask': round(ask, 2),
            'volume': volume,
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
        #     'bid_qty': bid_qty,
        #     'ask_qty': ask_qty,
        #     'volume': self.volume_counter,
        #     'timestamp': datetime.now()
        # }
    
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
