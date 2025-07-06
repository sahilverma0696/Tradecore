# Deprecated: All signal logic is now in vwap_strategy.py. This file is no longer used.
from src.logger_factory import get_logger
from src.core.order_manager import OrderManager

class SignalManager:
    def __init__(self, order_manager: OrderManager, instrument_config: dict):
        self.order_manager = order_manager
        self.instrument_config = instrument_config  # name -> {symbol, step, trail}
        self._logger = get_logger("SignalManager")

    # ------------------------------------------------------------------
    def handle_candle(self, name: str, candle: dict):
        self._check_candle(name, candle)

    # ------------------------------------------------------------------
    def _check_candle(self, name: str, candle: dict):
        ts = candle['timestamp']
        open_ = candle['open']
        close = candle['close']
        vwap = candle.get('vwap')
        if not vwap or name not in self.instrument_config:
            return
        cfg = self.instrument_config[name]
        if open_ < vwap and close > vwap and not self.order_manager.has_order(name):
            self._logger.info(f"BUY signal {name} {close}")
            self.order_manager.create_order(
                timestamp=ts,
                name=name,
                instrument=cfg['symbol'],
                step=cfg['step'],
                trail=cfg['trail'],
                side="BUY",
                candle=candle,
            )
        elif open_ > vwap and close < vwap and not self.order_manager.has_order(name):
            self._logger.info(f"SELL signal {name} {close}")
            self.order_manager.create_order(
                timestamp=ts,
                name=name,
                instrument=cfg['symbol'],
                step=cfg['step'],
                trail=cfg['trail'],
                side="SELL",
                candle=candle,
            )
