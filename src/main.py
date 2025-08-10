"""High-level wiring for VWAP trading system."""
from datetime import datetime
from src.logger_factory import get_logger
from src.config_manager import ConfigManager
from src.core.candle.candle_maker import CandleMaker
from src.core.order_manager import OrderManager
from src.core.executioner import Execute
from src.strategies.vwap_strategy import VwapStrategy
from src.strategies.exit_manager import ExitManager
from src.market.zerodha.zerodha_streamer import ZerodhaStreamer
from src.market.zerodha.quote_database import QuoteDatabase
from src.core.event_bus import EventBus, QuoteReceived, EntrySignal, ExitSignal

logger = get_logger("MAIN")


def build():
    logger.info("Starting VWAP trading system with event bus...")
    
    # Load configuration
    logger.info("Loading configuration...")
    cfg_mgr = ConfigManager()
    cfg = cfg_mgr.get()
    logger.info(f"Configuration loaded: {cfg}")
    if not cfg:
        logger.error("Configuration is empty or invalid. Exiting.")
        return
    
    # Initialize event bus
    event_bus = EventBus()
    logger.info("EventBus initialized")
    
    # Initialize core components
    logger.info("Initializing core components...")
    candle_maker = CandleMaker()
    logger.info("CandleMaker initialized.")
    
    order_mgr = OrderManager()
    logger.info("OrderManager initialized.")
    
    # Initialize strategy with configuration
    logger.info("Initializing VWAP strategy...")
    entry_strategy = VwapStrategy(config=cfg)
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

    # Subscribe to events
    def handle_quote_for_db(event: QuoteReceived):
        """Save quotes to database"""
        quote_dict = {
            'ts': event.timestamp,
            'name': event.symbol,
            'ltp': event.ltp,
            'timestamp': event.timestamp
        }
        quote_db.save_quote(quote_dict)
        
        # Update order manager with LTP for exit checking
        order_mgr.update_ltp(event.symbol, event.ltp, event.timestamp)

    def handle_entry_signal(event: EntrySignal):
        """Handle entry signals from strategy"""
        signal_data = {
            'signal': 'ENTER',
            'symbol': event.symbol,
            'side': event.side,
            'entry_price': event.entry_price,
            'entry_time': event.timestamp,
            'name': event.symbol,
            'entry_vwap': event.entry_vwap,
            'quantity': event.quantity,
            'steps': event.exit_steps,
            'candle': event.candle_data
        }
        order_mgr.handle_signal(signal_data)

    def handle_exit_signal(event: ExitSignal):
        """Handle exit signals"""
        signal_data = {
            'signal': 'EXIT',
            'symbol': event.symbol,
            'exit_price': event.exit_price,
            'exit_reason': event.exit_reason,
            'quantity': event.quantity,
            'timestamp': event.timestamp
        }
        order_mgr.handle_signal(signal_data)

    logger.info("Subscribing to events...")
    # Subscribe to events
    event_bus.subscribe(QuoteReceived, handle_quote_for_db)
    event_bus.subscribe(EntrySignal, handle_entry_signal)
    event_bus.subscribe(ExitSignal, handle_exit_signal)
    
    # Order manager sends orders to executioner
    order_mgr.register_handler(execer.execute_order)
    
    logger.info("Event subscriptions registered successfully.")
    
    logger.info("Starting system...")
    streamer.start()

    logger.info("System initialised – streaming started with event bus")


if __name__ == "__main__":
    build()
