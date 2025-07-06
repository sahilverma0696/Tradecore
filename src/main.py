"""High-level wiring for VWAP trading system."""
from datetime import datetime
from src.logger_factory import get_logger
from src.config_manager import ConfigManager
from src.core.candle_maker import CandleMaker
from src.core.order_manager import OrderManager
from src.core.executioner import Executioner
from src.strategies.vwap_strategy import VwapStrategy
from src.market.zerodha_streamer import ZerodhaStreamer

LOGGER = get_logger("MAIN")


def build():
    cfg_mgr = ConfigManager()
    cfg = cfg_mgr.get()

    candle_maker = CandleMaker()
    order_mgr = OrderManager()
    strategy = VwapStrategy()  # Use default or pass config as needed

    # --- streamer first ---
    streamer = ZerodhaStreamer(
        symbols=[int(s) for s in cfg['symbols']],
        api_key=cfg['api_key'],
        api_secret=cfg['api_secret'],
        name_symbol=cfg['name_symbol'],
        paper_trade=cfg.get('paper_trade', True),
    )

    # Handler for new candles: let strategy decide and create orders
    def handle_candle(name, candle):
        strategy.on_candle(name, candle)
        # If a new position is opened, create an order in order_mgr
        if name in strategy.positions and not order_mgr.has_order(name):
            pos = strategy.positions[name]
            order_mgr.create_order(
                timestamp=pos['entry_time'],
                name=name,
                instrument=cfg['name_symbol'][name],
                step=[s[0] for s in pos['steps']],
                trail=[0.1]*len(pos['steps']),  # Example: static trail, adjust as needed
                side=pos['side'],
                candle=candle
            )

    # Handler for new quotes: let strategy manage exits and update order_mgr
    def handle_quote(quote):
        name = quote['name']
        ltp = quote['ltp']
        timestamp = quote.get('timestamp', datetime.now())
        volume = quote.get('volume', 0)
        strategy.on_quote(name, ltp, volume, timestamp)
        order_mgr.update_ltp(name, ltp, timestamp)

    streamer.register_handler(handle_candle)
    streamer.register_handler(handle_quote)
    streamer.init_kite(cfg.get('access_token'))

    execer = Executioner(kite_client=streamer.get_kite(), paper_trade=cfg.get('paper_trade', True))
    order_mgr.on_order_created = lambda name, order, timestamp: execer.place_market(order.instrument, order.side)

    streamer.start()

    LOGGER.info("System initialised – streaming started")


if __name__ == "__main__":
    build()
