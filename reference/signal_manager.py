from order_manager import OrderManager
import logging
from logger_factory import get_logger

class SignalManager:
    def __init__(self, order_manager, instrument_config):
        """
        :param order_manager: Instance of OrderManager
        :param instrument_config: Dict of name -> config {symbol, name, step, trail}
        """
        self.order_manager = order_manager
        self.instrument_config = instrument_config
        self.logger = get_logger("SignalManager")
        self.logger.info("INIT for SignalManager")

    def handle_candle(self, name, candle):
        """
        Called by CandleMaker with each completed 5-min candle.
        Delegates to check_candle for signal evaluation.
        """
        self.check_candle(name,candle)

    def check_candle(self, name, candle):
        """
        Checks the candle for BUY or SELL signals and triggers order creation.
        """
        timestamp = candle['timestamp']
        open_ = candle['open']
        close = candle['close']
        vwap = candle['vwap']
        

        # self.logger.info(f"Checking candle for {name}: open={open_}, close={close}, vwap={vwap}")
        

        if not vwap or name not in self.instrument_config:
            # self.logger.warning(f"Skipping candle for {name}: Missing VWAP or config")
            return

        # --- BUY condition ---
        if open_ < vwap and close > vwap:
            if not self.order_manager.has_order(name):
                config = self.instrument_config[name]
                self.logger.info(f"TIMESTAMP {timestamp} BUY signal for {name}. ltp{close} Creating order.")
                self.order_manager.create_order(
                    timestamp=timestamp,
                    name=name,
                    instrument=config["symbol"],
                    step=config["step"],
                    trail=config["trail"],
                    side="BUY",
                    candle=candle
                )
            else:
                self.logger.debug(f"TIMESTAMP {timestamp} BUY signal for {name}, but order already exists.")

        # --- SELL condition ---
        elif open_ > vwap and close < vwap:
            if not self.order_manager.has_order(name):
                config = self.instrument_config[name]
                self.logger.info(f"TIMESTAMP {timestamp} SELL signal for {name}. ltp{close} Creating order.")
                self.order_manager.create_order(
                    timestamp=timestamp,
                    name=name,
                    instrument=config["symbol"],
                    step=config["step"],
                    trail=config["trail"],
                    side="SELL",
                    candle=candle
                )
            else:
                self.logger.debug(f"TIMESTAMP {timestamp} SELL signal for {name}, but order already exists.")
