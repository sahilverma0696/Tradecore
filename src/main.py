"""High-level wiring for VWAP trading system."""
from datetime import datetime
from src.logger_factory import get_logger
from src.config_manager import ConfigManager
from src.core.candle_maker import CandleMaker
from src.core.order_manager import OrderManager
from src.core.executioner import Execute
from src.strategies.vwap_strategy import VwapStrategy
from src.strategies.exit_manager import ExitManager
from src.market.zerodha.zerodha_streamer import ZerodhaStreamer
from src.market.zerodha.quote_database import QuoteDatabase

logger = get_logger("MAIN")


def build():
    logger.info("Starting VWAP trading system...")
    
    # Load configuration
    logger.info("Loading configuration...")
    cfg_mgr = ConfigManager()
    cfg = cfg_mgr.get()
    logger.info(f"Configuration loaded: {cfg}")
    if not cfg:
        logger.error("Configuration is empty or invalid. Exiting.")
        return
    
    # Initialize core components
    logger.info("Initializing core components...")
    candle_maker = CandleMaker()
    logger.info("CandleMaker initialized.")
    
    order_mgr = OrderManager()
    logger.info("OrderManager initialized.")
    
    # Initialize strategy with configuration
    logger.info("Initializing VWAP strategy...")
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

    # Wire exit manager to order manager
    order_mgr.set_exit_manager(exit_mgr)

    # Initialize streamer
    logger.info("Initializing ZerodhaStreamer...")
    # Initialize ZerodhaStreamer with configuration
    logger.info(f"Connecting to Zerodha with symbols: {cfg['symbols']}")
    if not cfg.get('symbols'):
        logger.error("No symbols configured for ZerodhaStreamer. Exiting.")
        return
    streamer = ZerodhaStreamer(
        symbols=[int(s) for s in cfg['symbols']],
        api_key=cfg['api_key'],
        api_secret=cfg['api_secret'],
        name_symbol=cfg['name_symbol'],
        paper_trade=cfg.get('paper_trade', True),
    )
    logger.info("ZerodhaStreamer initialized.")
    
    # Initialize executioner
    logger.info("Initializing executioner...")
    execer = streamer.init_kite(cfg.get('access_token'))
    logger.info("Executioner initialized.")
    
    # Initialize quote database
    logger.info("Initializing QuoteDatabase...")
    quote_db = QuoteDatabase(symbol=cfg.get('name_symbol'))
    logger.info("QuoteDatabase initialized.")

    # Handler for new quotes: save to DB and update order manager
    def handle_quote(quote):
        quote_db.save_quote(quote)
        name = quote['name']
        ltp = quote['ltp']
        timestamp = quote.get('timestamp', datetime.now())
        
        # Update order manager with LTP for exit checking
        order_mgr.update_ltp(name, ltp, timestamp)

    # Handler for new candles: let strategy decide on entries
    def handle_candle(name, candle):
        entry_strategy.on_candle(name, candle)
        order_mgr.update_candle(name, candle)

    logger.info("Registering handlers...")
    # Register handlers
    streamer.register_handler(handle_quote)
    streamer.register_handler(candle_maker.handle_quote_to_candle)
    candle_maker.register_handler(handle_candle)
    
    # Strategy sends entry signals to order manager
    entry_strategy.register_handler(order_mgr.handle_signal)
    
    # Order manager sends orders to executioner
    order_mgr.register_handler(execer.execute_order)
    
    logger.info("Handlers registered successfully.")
    
    logger.info("Initializing Kite with access token...")
    streamer.init_kite(cfg.get('access_token'))

    logger.info("Starting system...")
    streamer.start()

    logger.info("System initialised – streaming started")


if __name__ == "__main__":
    build()
