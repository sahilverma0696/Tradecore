from datetime import datetime
import time
from src.logger_factory import get_logger
from src.config_manager import ConfigManager

class Executioner:
    """Place orders through kite client (or simulate if paper_trade)."""
    def __init__(self, kite_client, *, paper_trade: bool, logger=None):
        self._kite = kite_client
        self._paper = paper_trade
        self._logger = logger or get_logger("Executioner")
        self._config_mgr = ConfigManager()
        self._config_mgr.register_watcher(self._on_cfg)
        self._set_cfg(self._config_mgr.get())

    # ------------------------------------------------------------------
    def _set_cfg(self, cfg):
        exec_cfg = cfg.get('execution', {})
        self._quantities = exec_cfg.get('quantities', {'default': 1})

    def _on_cfg(self, cfg):
        self._set_cfg(cfg)
        self._logger.info("Executioner config updated")

    # ------------------------------------------------------------------
    def _qty(self, symbol):
        return self._quantities.get(symbol, self._quantities.get('default', 1))

    def place_market(self, symbol: str, side: str):
        qt = self._qty(symbol)
        if self._paper:
            self._logger.info(f"PAPER | {side} {qt} {symbol}")
            return True
        try:
            resp = self._kite.place_order(
                variety=self._kite.VARIETY_REGULAR,
                exchange=self._kite.EXCHANGE_NFO,
                tradingsymbol=symbol,
                transaction_type=self._kite.TRANSACTION_TYPE_BUY if side == 'BUY' else self._kite.TRANSACTION_TYPE_SELL,
                quantity=qt,
                order_type=self._kite.ORDER_TYPE_MARKET,
                product=self._kite.PRODUCT_MIS,
            )
            self._logger.info(f"LIVE ORDER placed id={resp}")
            return True
        except Exception as e:
            self._logger.error(f"Order failed: {e}")
            return False
