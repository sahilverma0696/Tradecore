from datetime import datetime
from src.logger_factory import get_logger

class ExitManager:
    """Implements RISK / RETRACE exits based on VWAP, step and trail."""
    def __init__(self, order_manager):
        self.order_manager = order_manager
        self._logger = get_logger("ExitManager")
        self._callback = None  # external exit handler

    def register_exit_handler(self, cb):
        if callable(cb):
            self._callback = cb

    # ------------------------------------------------------------------
    def handle_quote(self, quote: dict):
        name = quote['name']
        ltp = quote['ltp']
        order = self.order_manager.get_order(name)
        if not order:
            return
        order.set_ltp(ltp)
        candle = order.get_current_candle()
        if not candle or candle.get('vwap') is None:
            return
        vwap = candle['vwap']
        side = order.get_side()
        # RISK exit – cross back over VWAP
        if (side == 'BUY' and ltp < vwap) or (side == 'SELL' and ltp > vwap):
            self._trigger_exit(order, 'RISK', ltp)
            return
        # RETRACE exit – step / trail based
        order.update_step()
        step_pct = order.get_current_step()
        trail_pct = order.get_current_trail()
        if side == 'BUY':
            peak = order.get_max_price()
            if ltp > peak:
                order.set_max_price(ltp)
            exit_level = max(order.get_entry_price() * (1 + step_pct), order.get_max_price() * (1 - trail_pct))
            if ltp <= exit_level:
                self._trigger_exit(order, 'RETRACE', exit_level)
        else:
            trough = order.get_min_price()
            if ltp < trough or trough == 0:
                order.set_min_price(ltp)
            exit_level = min(order.get_entry_price() * (1 - step_pct), order.get_min_price() * (1 + trail_pct))
            if ltp >= exit_level:
                self._trigger_exit(order, 'RETRACE', exit_level)

    # ------------------------------------------------------------------
    def _trigger_exit(self, order, reason: str, exit_price: float):
        ts = datetime.now()
        self._logger.info(f"EXIT {reason} {order.get_name()} price={exit_price}")
        if callable(self._callback):
            try:
                self._callback(order, reason)
            except Exception as e:
                self._logger.error(f"exit callback error: {e}")
        self.order_manager.remove_order(order.get_name(), ts, reason, exit_price)
