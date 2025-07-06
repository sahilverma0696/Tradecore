"""High-level wiring for VWAP trading system."""
from datetime import datetime
from src.logger_factory import get_logger
from src.config_manager import ConfigManager
from src.core.candle_maker import CandleMaker
from src.core.order_manager import OrderManager
from src.executioner import Execute
from src.strategies.vwap_strategy import VwapStrategy
from src.market.zerodha_streamer import ZerodhaStreamer

LOGGER = get_logger("MAIN")


def build():
    cfg_mgr = ConfigManager()
    cfg = cfg_mgr.get()

    candle_maker = CandleMaker()
    order_mgr = OrderManager()
    strategy = VwapStrategy(config=cfg)  # Pass config

    # --- streamer first ---
    streamer = ZerodhaStreamer(
        symbols=[int(s) for s in cfg['symbols']],
        api_key=cfg['api_key'],
        api_secret=cfg['api_secret'],
        name_symbol=cfg['name_symbol'],
        paper_trade=cfg.get('paper_trade', True),
    )

    # Handler for new quotes: save to DB, send to CandleMaker, and to strategy for exit logic
    def handle_quote(quote):
        candle_maker.handle_quote(quote)
        name = quote['name']
        ltp = quote['ltp']
        timestamp = quote.get('timestamp', datetime.now())
        volume = quote.get('volume', 0)
        strategy.on_quote(name, ltp, volume, timestamp)
        order_mgr.update_ltp(name, ltp, timestamp)

    # Handler for new candles: let strategy decide and create orders
    def handle_candle(name, candle):
        strategy.on_candle(name, candle)
        pos = strategy.positions.get(name)
        if pos:
            existing_order = order_mgr.get_order(name)
            if existing_order:
                if existing_order.get_side() != pos['side']:
                    order_mgr.remove_order(name, candle['timestamp'], "DIRECTION_SWITCH", candle['close'])
            if not order_mgr.has_order(name):
                order = order_mgr.create_order(
                    timestamp=pos['entry_time'],
                    name=name,
                    instrument=cfg['name_symbol'][name] if isinstance(cfg['name_symbol'], dict) else cfg['name_symbol'],
                    step=[s[0] for s in pos['steps']],
                    trail=[cfg.get('exit_max_pct', 0.01)]*len(pos['steps']),
                    side=pos['side'],
                    candle=candle,
                    quantity=pos['quantity']
                )
                # Route order entry through Execute
                if order:
                    direction = "B" if order.get_side() == "BUY" else "S"
                    execer.execute_order(order.instrument, direction, pos['entry_time'])

    streamer.register_handler(handle_quote)
    candle_maker.register_handler(handle_candle)
    streamer.init_kite(cfg.get('access_token'))

    execer = Execute(logger=LOGGER, excel_logger=None, expiry=None, client=streamer.get_kite())

    # Remove legacy on_order_created callback, as all order placement is now routed via handle_candle above

    streamer.start()

    LOGGER.info("System initialised – streaming started")


if __name__ == "__main__":
    build()
