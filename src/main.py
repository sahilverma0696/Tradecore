"""High-level wiring for VWAP trading system.

Usage:
- To use Zerodha, set "market": "zerodha" in trading_config.json.
- To use Binance, set "market": "binance" in trading_config.json.
- Each market has its own config section in trading_config.json.
"""

from datetime import datetime
from src.logger_factory import get_logger
from src.config_manager import ConfigManager
from src.core.candle.candle_factory import get_candle_maker
from src.core.order_manager import OrderManager
from src.execute.execute_factory import get_execute
from src.strategies.vwap_strategy import VwapStrategy
from src.strategies.exit_manager import ExitManager
from src.system_config import get_streamer
from src.data_store.quote_database_factory import get_quote_database
from src.core.plotting.live_chart_server import LiveChartServer
import os
import traceback

logger = get_logger("MAIN")


def build():
    logger.info("Starting VWAP trading system...")
    
    # Load configuration
    logger.info("Loading configuration...")
    # Initialize config manager and load config
    cfg_mgr = ConfigManager()
    cfg = cfg_mgr.get()
    logger.info(f"Configuration loaded: {cfg}")
    if not cfg:
        logger.error("Configuration is empty or invalid. Exiting.")
        return

    # --- streamer first ---
    logger.info("Initializing streamer...")
    if not cfg.get('symbols'):
        logger.error("No symbols configured for streamer. Exiting.")
        return
    market = cfg.get('market', 'zerodha')
    logger.info(f"Selected market: {market}")
    streamer = get_streamer(cfg)
    logger.info(f"{market.capitalize()} streamer initialized.")

    # Initialize core components
    logger.info("Initializing core components...")
    # Initialize candle maker using factory
    candle_maker = get_candle_maker(cfg)
    logger.info(f"CandleMaker initialized: {type(candle_maker).__name__}")
    
    
    # Initialize order manager and strategy
    order_mgr = OrderManager()
    logger.info("OrderManager initialized.")
    
    
    # Initialize strategy with configuration
    logger.info("Initializing VWAP strategy...")
    # Initialize strategy with configuration
    entry_strategy = VwapStrategy(config=cfg)  # Pass config
    logger.info("VWAPStrategy initialized.")
    
    # Initialize exit manager
    logger.info("Initializing ExitManager...")
    exit_mgr = ExitManager(
        exit_steps=cfg.get('exit_steps'),
        reterival_exit=cfg.get('reterival_exit'),
        default_quantity=cfg.get('default_quantity'),
        market_close=cfg.get('market_close'),
    )
    logger.info("ExitManager initialized.")
    


    # Initialize executioner using factory
    logger.info("Initializing executioner...")
    try:
        execer = get_execute(cfg, streamer)
    except Exception as e:
        logger.error(f"Failed to initialize executioner: {e}")
        return
    logger.info("Executioner initialized.")
    
    order_mgr.register_handler(
        execer.execute_order
    )  # Register order creation handler with executioner
    logger.info("OrderManager handler registered with Executioner.")
    
    # Initialize quote database using factory
    logger.info("Initializing QuoteDatabase...")
    quote_db = get_quote_database(cfg)
    logger.info("QuoteDatabase initialized.")

    # Initialize the chart server
    chart_server = LiveChartServer(max_candles=100, port=8080)

    # Handler for new quotes: save to DB, send to CandleMaker, to strategy for exit logic, and to chart for live price
    def handle_quote(quote):
        logger.debug(f"handle_quote received: {quote}")
        quote_db.save_quote(quote)  # Save the full quote to the database
        name = quote['name']
        ltp = quote['ltp']
        timestamp = quote.get('timestamp', datetime.now())
        volume = quote.get('volume', 0)
        order_mgr.update_ltp(name, ltp, timestamp) 
        
        # Add real-time price update to chart server
        chart_server.add_quote(quote)

    # Handler for new candles: let strategy decide and create orders
    def handle_candle(name, candle):
        logger.info(f"Processing new candle for {name}: OHLC({candle['open']:.2f},{candle['high']:.2f},{candle['low']:.2f},{candle['close']:.2f}) VWAP({candle.get('vwap', 'N/A')}) Volume({candle.get('volume', 0)}) at {candle['timestamp']}")
        
        entry_strategy.on_candle(name, candle)
        order_mgr.update_candle(name, candle)  # Update order manager with new candle data
        
        # Add candle to chart server with logging
        chart_server.add_candle(name, candle)
        logger.debug(f"Candle data sent to chart server for {name}")
        
        ## TODO: add candles to data visualisation classes
        



    logger.info("Registering handlers for quotes and candles...")
    # Register handlers for quotes and candles
    streamer.register_handler(handle_quote)
    streamer.register_handler(candle_maker.handle_quote_to_candle)
    candle_maker.register_handler(handle_candle)
    
    entry_strategy.register_handler(order_mgr.get_signal)
    exit_mgr.register_handler(order_mgr.get_signal)
    order_mgr.register_handler(execer.execute_order)
    logger.info("Handlers registered successfully.")
    market = cfg.get('market', 'zerodha')  # <-- Add this line to define 'market'

    if market == 'zerodha':
        logger.info("Initializing Kite with access token...")
        streamer.init_kite(cfg.get('access_token'))
    elif market == 'binance':
        logger.info("Binance selected: no init_kite required.")

    logger.info("Starting system...")
    streamer.start()
    logger.info("System initialised – streaming started")

    # Start the chart server
    chart_server.start_server(open_browser=True)

    # Wait for Binance streamer thread to finish if market is binance
    if market == 'binance':
        if hasattr(streamer, '_thread') and streamer._thread is not None:
            logger.info("Waiting for Binance streamer thread to finish...")
            streamer._thread.join()
            logger.info("Binance streamer thread finished.")
        # Optionally stop DB thread
        if hasattr(quote_db, 'stop'):
            quote_db.stop()


if __name__ == "__main__":
    '''
    1. Basic config needed to setup the system
    2. The mode selection in the system
        - This is where you can set the mode to 'live' or 'paper' trading, or backtesting
        - The mode will be given by arguments, which will be parsed by switch case here
    3. The build function will be called to start the system
    4. The system is built on streaming data which can be from a provider or stored db, so it will start streaming quotes
    5. From quotes, data will be processed to create candles, which will then be used by the strategy to make decisions
    6. The strategy will create orders based on the candles and the current market conditions
    7. The orders will be executed by the executioner, which will handle the order
    8. The system will log all the actions taken, and the results of those actions
    9. The system will run in a given time frame, which can be set in the config
    '''
    
    '''
    1. Live trading mode
    2. Paper trading mode
    3. Backtesting mode
    '''
    try:
        build()
    except Exception as e:
        logger.error(f"Uncaught exception in main: {e}\n{traceback.format_exc()}")