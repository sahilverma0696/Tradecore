from quotes import QuoteStreamer
from candle import CandleMaker
from order_manager import OrderManager
from exit_manager import ExitManager
from signal_manager import SignalManager
from logger_factory import get_logger
from utils import load_instrument_config
from plotter import CandlePlotter
from datetime import datetime
from typing import Optional, Dict, Any


# Constants
INSTRUMENT_CONFIG_PATH = "instruments.json"
DB_FILE = "../../data/upstox/upstox_ltp.db"
QUOTE_TABLE = "quotes_20250630"
TARGET_DATE = "2025-06-30"
TARGET_NAME = "NIFTY 25600 CE 03 JUL 25"
CANDLE_LOG_CSV = "logs/candles.csv"

# Main execution block
if __name__ == "__main__":
    logger = get_logger("Main")
    logger.info("Initializing components...")

    # Load instrument configs
    raw_configs = load_instrument_config(INSTRUMENT_CONFIG_PATH)
    instrument_configs = {item["name"]: item for item in raw_configs}
    
    # Debug: Print loaded instrument configs
    logger.info("Loaded instrument configurations:")
    for name, config in instrument_configs.items():
        logger.info(f"  {name}:")
        logger.info(f"    symbol: {config.get('symbol')}")
        logger.info(f"    step: {config.get('step')}")
        logger.info(f"    trail: {config.get('trail')}")

    # Create plotter first as other components will need it
    plotter = CandlePlotter()
    
    # Track active trades
    active_trades: Dict[str, Dict[str, Any]] = {}
    
    # Managers
    order_manager = OrderManager()
    exit_manager = ExitManager(order_manager)
    signal_manager = SignalManager(order_manager=order_manager, instrument_config=instrument_configs)
    
    # Trade tracking functions
    def on_order_created(name: str, order: Any, timestamp: str):
        """Track when a new order is created"""
        active_trades[name] = {
            'entry_timestamp': timestamp,
            'entry_price': order.entry_price,
            'side': order.side,
            'exit_timestamp': None,
            'exit_price': None,
            'exit_reason': None
        }
        # Add to plotter
        plotter.add_trade(
            timestamp=timestamp,
            side=order.side,
            entry_price=order.entry_price
        )
    
    def on_order_exited(name: str, order: Any, timestamp: str, exit_reason: str):
        """Track when an order is exited"""
        if name in active_trades:
            active_trades[name].update({
                'exit_timestamp': timestamp,
                'exit_price': order.ltp,  # Use last traded price as exit
                'exit_reason': exit_reason
            })
            # Update plotter with exit
            plotter.add_trade(
                timestamp=timestamp,
                side=active_trades[name]['side'],
                entry_price=active_trades[name]['entry_price'],
                exit_price=order.ltp,
                exit_reason=exit_reason
            )

    # CandleMaker setup
    candle_maker = CandleMaker(csv_file=CANDLE_LOG_CSV) 
    candle_maker.register_handler(plotter.handle_candle)
    candle_maker.register_handler(signal_manager.handle_candle)
    

    # QuoteStreamer setup (do not call .stream_quotes() until handlers are registered)
    quote_streamer = QuoteStreamer(DB_FILE, QUOTE_TABLE, TARGET_DATE, TARGET_NAME)

    # Exit handler registration
    def on_exit(order, reason):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        logger.info(f"[EXIT] {order.name} exited due to {reason} at {timestamp}")
        # Track the exit before removing the order
        on_order_exited(order.name, order, timestamp, reason)
        order_manager.remove_order(name=order.name, timestamp=timestamp, exit_reason=reason)

    exit_manager.register_exit_handler(on_exit)

    # Register all handlers before streaming
    quote_streamer.register_handler(candle_maker.handle_quote)
    quote_streamer.register_handler(exit_manager.handle_ltp)
    
    # Register order creation handler
    order_manager.on_order_created = on_order_created

    logger.info("All handlers registered. Starting quote stream...")
    quote_streamer.stream_quotes()
    logger.info("Quote streaming completed.")
    
    # Once all quotes are processed:
    logger.info(f"Saving plot with {len(active_trades)} trades...")
    plotter.save_plot()
    
    # Save trades to CSV for reference
    if active_trades:
        import pandas as pd
        trades_df = pd.DataFrame(active_trades).T
        trades_csv = "logs/trades_summary.csv"
        trades_df.to_csv(trades_csv, index_label='instrument')
        logger.info(f"Saved trades summary to {trades_csv}")
    
    logger.info("Backtest completed successfully")



