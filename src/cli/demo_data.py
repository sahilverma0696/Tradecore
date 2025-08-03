"""Demo data generator for testing the dashboard."""

import time
import random
import threading
from datetime import datetime, timedelta

from src.core.event_bus import EventBus, QuoteReceived, CandleGenerated, EntrySignal, ExitSignal, OrderExecuted
from src.logger_factory import get_logger


class DemoDataGenerator:
    """Generates demo trading data for dashboard testing."""
    
    def __init__(self):
        self.event_bus = EventBus()
        self.logger = get_logger("DemoDataGenerator")
        self.symbols = ["NIFTY", "BANKNIFTY", "FINNIFTY", "RELIANCE", "TCS"]
        self.base_prices = {
            "NIFTY": 18500,
            "BANKNIFTY": 42000,
            "FINNIFTY": 19000,
            "RELIANCE": 2400,
            "TCS": 3800
        }
        self.current_prices = self.base_prices.copy()
        self.running = False
        self.active_positions = {}
        
    def start(self):
        """Start generating demo data."""
        self.running = True
        self.logger.info("Starting demo data generation...")
        
        # Start various data generation threads
        threading.Thread(target=self._generate_quotes, daemon=True).start()
        threading.Thread(target=self._generate_candles, daemon=True).start()
        threading.Thread(target=self._generate_signals, daemon=True).start()
        
    def stop(self):
        """Stop generating demo data."""
        self.running = False
        self.logger.info("Stopped demo data generation")
    
    def _generate_quotes(self):
        """Generate random quote data."""
        while self.running:
            for symbol in self.symbols:
                # Random price movement
                change_pct = random.uniform(-0.5, 0.5) / 100
                new_price = self.current_prices[symbol] * (1 + change_pct)
                self.current_prices[symbol] = new_price
                
                quote_event = QuoteReceived(
                    timestamp=datetime.now(),
                    source="DemoStreamer",
                    symbol=symbol,
                    instrument=random.randint(100000, 999999),
                    ltp=new_price,
                    volume=random.randint(1000, 50000),
                    last_quantity=random.randint(1, 100),
                    change=change_pct * 100,
                    raw_data={"demo": True}
                )
                
                self.event_bus.publish(quote_event)
                
            time.sleep(0.5)  # 500ms between quote updates
    
    def _generate_candles(self):
        """Generate candle data."""
        while self.running:
            for symbol in self.symbols:
                base_price = self.current_prices[symbol]
                open_price = base_price * random.uniform(0.995, 1.005)
                close_price = base_price * random.uniform(0.995, 1.005)
                high_price = max(open_price, close_price) * random.uniform(1.0, 1.01)
                low_price = min(open_price, close_price) * random.uniform(0.99, 1.0)
                volume = random.randint(10000, 100000)
                vwap = (high_price + low_price + close_price) / 3
                
                candle_data = {
                    "timestamp": datetime.now(),
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                    "vwap": vwap
                }
                
                candle_event = CandleGenerated(
                    timestamp=datetime.now(),
                    source="DemoCandleMaker",
                    symbol=symbol,
                    candle_data=candle_data,
                    timeframe="5m"
                )
                
                self.event_bus.publish(candle_event)
                
            time.sleep(5)  # 5 seconds between candle updates
    
    def _generate_signals(self):
        """Generate entry and exit signals."""
        while self.running:
            # Randomly generate entry signals
            if random.random() < 0.1 and len(self.active_positions) < 3:  # 10% chance
                symbol = random.choice(self.symbols)
                if symbol not in self.active_positions:
                    side = random.choice(["BUY", "SELL"])
                    entry_price = self.current_prices[symbol]
                    
                    entry_event = EntrySignal(
                        timestamp=datetime.now(),
                        source="DemoStrategy",
                        symbol=symbol,
                        side=side,
                        entry_price=entry_price,
                        entry_vwap=entry_price * 0.999,
                        quantity=random.choice([25, 50, 75, 100]),
                        exit_steps=[(0.01, 0.5), (0.02, 0.5)],
                        strategy_name="DemoStrategy",
                        candle_data={"close": entry_price}
                    )
                    
                    self.event_bus.publish(entry_event)
                    self.active_positions[symbol] = {
                        "entry_time": datetime.now(),
                        "side": side,
                        "entry_price": entry_price
                    }
                    
                    # Generate order executed event
                    order_event = OrderExecuted(
                        timestamp=datetime.now(),
                        source="DemoExecutioner",
                        symbol=symbol,
                        side=side,
                        price=entry_price,
                        quantity=entry_event.quantity,
                        order_id=f"DEMO{random.randint(1000, 9999)}",
                        execution_type="ENTRY"
                    )
                    self.event_bus.publish(order_event)
            
            # Randomly generate exit signals for active positions
            for symbol in list(self.active_positions.keys()):
                pos = self.active_positions[symbol]
                age = datetime.now() - pos["entry_time"]
                
                # Exit after some time or randomly
                if age > timedelta(seconds=30) or random.random() < 0.05:  # 5% chance or 30 seconds
                    exit_price = self.current_prices[symbol]
                    exit_reasons = ["STEP_1", "STEP_2", "TRAIL", "TIME", "MANUAL"]
                    
                    exit_event = ExitSignal(
                        timestamp=datetime.now(),
                        source="DemoExitManager",
                        symbol=symbol,
                        exit_price=exit_price,
                        exit_reason=random.choice(exit_reasons),
                        quantity=75
                    )
                    
                    self.event_bus.publish(exit_event)
                    
                    # Generate order executed event
                    order_event = OrderExecuted(
                        timestamp=datetime.now(),
                        source="DemoExecutioner",
                        symbol=symbol,
                        side="SELL" if pos["side"] == "BUY" else "BUY",
                        price=exit_price,
                        quantity=75,
                        order_id=f"DEMO{random.randint(1000, 9999)}",
                        execution_type="EXIT"
                    )
                    self.event_bus.publish(order_event)
                    
                    del self.active_positions[symbol]
                    
            time.sleep(2)  # Check every 2 seconds


def start_demo_data_generator():
    """Start the demo data generator."""
    generator = DemoDataGenerator()
    generator.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        generator.stop()


if __name__ == "__main__":
    start_demo_data_generator()
