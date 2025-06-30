from typing import Dict
from datetime import datetime
from src.logger_factory import get_logger
from src.core.order_object import OrderObject
from src.core.order_logger import OrderLogger

class OrderManager:
    """Manages active orders and delegates logging."""

    def __init__(self, log_dir: str = "logs"):
        self._orders: Dict[str, OrderObject] = {}
        self._logger = get_logger("OrderManager")
        self._order_logger = OrderLogger(log_dir)
        self.on_order_created = None  # callback(name, order, timestamp)

    # ------------------------------------------------------------------
    def create_order(self, timestamp: datetime, name: str, instrument: str, step, trail, side: str, candle=None):
        if name in self._orders:
            self._logger.warning(f"Order {name} already exists")
            return self._orders[name]
        order = OrderObject(name, instrument, step, trail, side, candle)
        self._orders[name] = order
        self._logger.info(f"Created order {name}")
        self._order_logger.log_entry(order)
        if callable(self.on_order_created):
            try:
                self.on_order_created(name=name, order=order, timestamp=timestamp)
            except Exception as cb_err:
                self._logger.error(f"on_order_created error: {cb_err}")
        return order

    def has_order(self, name: str) -> bool:
        return name in self._orders

    def get_order(self, name: str):
        return self._orders.get(name)

    def update_ltp(self, name: str, ltp: float, timestamp=None):
        if name in self._orders:
            self._orders[name].set_ltp(ltp, timestamp)

    def update_candle(self, name: str, candle: dict, timestamp=None):
        if name in self._orders:
            self._orders[name].set_current_candle(candle, timestamp)

    def remove_order(self, name: str, timestamp: datetime, exit_reason: str, exit_price: float):
        order = self._orders.pop(name, None)
        if order:
            self._logger.info(f"Order {name} exited: {exit_reason}")
            self._order_logger.log_exit(order, exit_reason, exit_price)
        return order

    # Helper to iterate
    def all_orders(self):
        return self._orders.values()
