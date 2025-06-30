"""High-level wiring for VWAP trading system."""
from datetime import datetime
from src.logger_factory import get_logger
from src.config_manager import ConfigManager
from src.core.candle_maker import CandleMaker
from src.core.order_manager import OrderManager
from src.core.executioner import Executioner
from src.core.exit_manager import ExitManager
from src.core.signal_manager import SignalManager
from src.market.zerodha_streamer import ZerodhaStreamer

LOGGER = get_logger("MAIN")


def build():
    cfg_mgr = ConfigManager()
    cfg = cfg_mgr.get()

    candle_maker = CandleMaker()
    order_mgr = OrderManager()
    exit_mgr = ExitManager(order_mgr)

    # --- Handlers chain ---
    candle_maker.register_handler(SignalManager(order_mgr, cfg['instrument_config']).handle_candle)

    streamer = ZerodhaStreamer(
        symbols=[int(s) for s in cfg['symbols']],
        api_key=cfg['api_key'],
        api_secret=cfg['api_secret'],
        name_symbol=cfg['name_symbol'],
        paper_trade=cfg.get('paper_trade', True),
    )
    streamer.register_handler(candle_maker.handle_quote)
    streamer.register_handler(exit_mgr.handle_quote)
    streamer.init_kite(cfg.get('access_token'))
    streamer.start()

    LOGGER.info("System initialised – streaming started")


if __name__ == "__main__":
    build()
