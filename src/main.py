"""High-level wiring for VWAP trading system."""
from datetime import datetime
import signal
from threading import Event

from src.logger_factory import get_logger
from src.config_manager import ConfigManager
from src.system_config_manager import SystemConfigManager
from src.core.candle_maker import CandleMaker
from src.core.order_manager import OrderManager
from src.core.executioner import Execute
from src.strategies.vwap_strategy import VwapStrategy
from src.strategies.exit_manager import ExitManager
from src.market.zerodha.quote_database import QuoteDatabase
from src.core.event_bus import EventBus, QuoteReceived, EntrySignal, ExitSignal
from src.core.streamer import StreamerFactory

# Global shutdown event
shutdown_event = Event()

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger = get_logger("Main")
    logger.info("Shutdown signal received, stopping all components...")
    shutdown_event.set()

def create_streamer_from_config(system_config: SystemConfigManager, trading_config: dict):
    """Create streamer using factory based on system configuration."""
    streamer_config = system_config.get_streamer_config()
    streamer_type = streamer_config['type']
    
    # Get symbols from trading config
    symbols = trading_config.get('symbols', [])
    if not symbols:
        raise ValueError("No symbols configured in trading_config.json")
    
    # Prepare streamer-specific configuration
    config = {}
    
    if streamer_type == 'zerodha':
        config.update({
            'api_key': trading_config.get('api_key'),
            'api_secret': trading_config.get('api_secret'),
            'name_symbol': trading_config.get('name_symbol'),
            'paper_trade': trading_config.get('paper_trade', True)
        })
        
        # Validate required Zerodha config
        required = ['api_key', 'api_secret', 'name_symbol']
        missing = [k for k in required if not config.get(k)]
        if missing:
            raise ValueError(f"Missing Zerodha configuration: {missing}")
            
    elif streamer_type == 'offline':
        config.update(streamer_config.get('config', {}))
        config.update({
            'base_price': 18500.0,  # Default NIFTY price
            'tick_interval': 1.0
        })
    
    elif streamer_type == 'binance':
        config.update(streamer_config.get('config', {}))
    
    # Create streamer using factory
    logger.info(f"Creating {streamer_type} streamer with symbols: {symbols}")
    return StreamerFactory.create_streamer(streamer_type, symbols, config)

def build():
    logger = get_logger("MAIN")
    logger.info("🚀 Starting Algorithmic Trading System...")
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Load configurations
        logger.info("Loading configuration...")
        cfg_mgr = ConfigManager()
        cfg = cfg_mgr.get()
        
        system_cfg_mgr = SystemConfigManager()
        
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

        # Initialize streamer using factory
        logger.info("Initializing streamer using factory...")
        try:
            streamer = create_streamer_from_config(system_cfg_mgr, cfg)
            logger.info(f"Streamer initialized: {type(streamer).__name__}")
        except Exception as e:
            logger.error(f"Failed to create streamer: {e}")
            return
        
        # Initialize executioner (legacy support)
        logger.info("Initializing executioner...")
        if hasattr(streamer, 'init_kite'):
            # Zerodha streamer with Kite integration
            execer = streamer.init_kite(cfg.get('access_token'))
        else:
            # Generic executor
            execer = Execute(
                client=None,
                paper_trade=cfg.get('paper_trade', True),
                logger=logger
            )
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
        
        # Start streamer using BaseStreamer interface
        if hasattr(streamer, 'start'):
            streamer.start()
        elif hasattr(streamer, 'connect'):
            # Legacy interface
            streamer.connect()
        else:
            logger.error("Streamer does not have start() or connect() method")
            return

        logger.info("System initialised – streaming started with event bus")
        
        # Main loop
        logger.info("🔄 System running... Press Ctrl+C to stop")
        
        while not shutdown_event.is_set():
            try:
                # System health check
                if hasattr(streamer, 'get_status'):
                    status = streamer.get_status()
                    if not status.get('is_running', False):
                        logger.warning("Streamer is not active")
                
                # Check executor stats
                if hasattr(executioner, 'get_execution_stats'):
                    stats = executioner.get_execution_stats()
                    logger.debug(f"Executor stats: {stats}")
                
                # Sleep and check for shutdown
                shutdown_event.wait(timeout=10.0)
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
                
    except Exception as e:
        logger.error(f"Critical error in main: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    finally:
        # Cleanup
        logger.info("🛑 Shutting down system...")
        
        # Stop streamer
        try:
            if hasattr(streamer, 'stop'):
                streamer.stop()
            elif hasattr(streamer, 'disconnect'):
                streamer.disconnect()
        except Exception as e:
            logger.error(f"Error stopping streamer: {e}")
            
        # Stop other components
        try:
            if hasattr(order_manager, 'stop'):
                order_manager.stop()
        except Exception as e:
            logger.error(f"Error stopping order manager: {e}")
            
        logger.info("✅ System shutdown complete")

if __name__ == "__main__":
    build()
