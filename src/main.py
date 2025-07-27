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
    # Initialize config manager and load config
    cfg_mgr = ConfigManager()
    cfg = cfg_mgr.get()
    logger.info(f"Configuration loaded: {cfg}")
    if not cfg:
        logger.error("Configuration is empty or invalid. Exiting.")
        return
    
    
    # Initialize core components
    logger.info("Initializing core components...")
    # Initialize candle maker
    candle_maker = CandleMaker()
    logger.info("CandleMaker initialized.")
    
    
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
        exit_max_pct=cfg.get('exit_max_pct', 0.05),
        default_quantity=cfg.get('default_quantity', 75),
        market_close=cfg.get('market_close'),
        output_file=cfg.get('output_file', "trades.csv")
    )
    logger.info("ExitManager initialized.")
    


    # --- streamer first ---
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
    execer = Execute(excel_logger=None, expiry=None, client=streamer.get_kite())
    logger.info("Executioner initialized.")
    
    order_mgr.register_handler(
        execer.execute_order
    )  # Register order creation handler with executioner
    logger.info("OrderManager handler registered with Executioner.")
    
    # Initialize quote database
    logger.info("Initializing QuoteDatabase...")
    quote_db = QuoteDatabase(symbol=cfg.get('name_symbol'))
    logger.info("QuoteDatabase initialized.")

    # Handler for new quotes: save to DB, send to CandleMaker, and to strategy for exit logic
    def handle_quote(quote):
        
        quote_db.save_quote(quote)  # Save the full quote to the database
        
        name = quote['name']
        ltp = quote['ltp']
        timestamp = quote.get('timestamp', datetime.now())
        volume = quote.get('volume', 0)
        exit_mgr.vwap_on_quote(name, ltp, volume, timestamp)
        # order_mgr.update_ltp(name, ltp, timestamp)  ## Update this through vwap strategy

    # Handler for new candles: let strategy decide and create orders
    def handle_candle(name, candle):
        entry_strategy.on_candle(name, candle)
        
        ## TODO: add candles to data visualisation classes
        
        # pos = strategy.positions.get(name)
        # if pos:
        #     existing_order = order_mgr.get_order(name)
        #     if existing_order:
        #         if existing_order.get_side() != pos['side']:
        #             order_mgr.remove_order(name, candle['timestamp'], "DIRECTION_SWITCH", candle['close'])
        #     if not order_mgr.has_order(name):
        #         order = order_mgr.create_order(
        #             timestamp=pos['entry_time'],
        #             name=name,
        #             instrument=cfg['name_symbol'][name] if isinstance(cfg['name_symbol'], dict) else cfg['name_symbol'],
        #             step=[s[0] for s in pos['steps']],
        #             trail=[cfg.get('exit_max_pct', 0.01)]*len(pos['steps']),
        #             side=pos['side'],
        #             candle=candle,
        #             quantity=pos['quantity']
        #         )
        #         # Route order entry through Execute
        #         if order:
        #             direction = "B" if order.get_side() == "BUY" else "S"
        #             execer.execute_order(order.instrument, direction, pos['entry_time'])

    logger.info("Registering handlers for quotes and candles...")
    streamer.register_handler(handle_quote)
    streamer.register_handler(candle_maker.handle_quote_to_candle)
    candle_maker.register_handler(handle_candle)
    logger.info("Initializing Kite with access token...")
    streamer.init_kite(cfg.get('access_token'))


    logger.info("Starting system...")
    streamer.start()

    logger.info("System initialised – streaming started")


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
    build()
