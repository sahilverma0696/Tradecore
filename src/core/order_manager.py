from typing import Dict
from datetime import datetime
from src.logger_factory import get_logger
from src.core.order_object import OrderObject
from src.core.order_logger import OrderLogger

class OrderManager:
    """Manages active orders and delegates logging."""

    def __init__(self, log_dir: str = "logs"):
        self._orders: Dict[str, OrderObject] = {}   # instrument -> OrderObject
        self._logger = get_logger("OrderManager")
        self._order_logger = OrderLogger(log_dir)
        self._handlers = []  # callback(name, order, timestamp)
        self._logger.info("OrderManager initialized")
        
    def register_handler(self, cb):
        if callable(cb):
            self._logger.debug(f"Registering handler {cb.__name__}")
            self._handlers.append(cb)
    
    def get_signal(self, signal: str, instrument: str):
        """ Decides based on the singal, what to do with the order. """
        if signal == "ENTER":
            self._logger.info(f"Received ENTER signal for instrument: {instrument}")
            # Create a new order or handle existing ones
            pass
        elif signal == "EXIT":
            self._logger.info(f"Received EXIT signal for instrument: {instrument}")
            pass
        else:
            self._logger.warning(f"Unknown signal: {signal} for instrument: {instrument}")
            return None

    # ------------------------------------------------------------------
    def create_order(self, timestamp: datetime, name: str, instrument: str, step, trail, side: str, candle=None, quantity=None):
        # Ensure only one direction per instrument
        existing_order = self._orders.get(name)
        if existing_order:
            if existing_order.get_side() != side:
                # Remove existing order before new direction
                self._logger.info(f"Switching direction for order {name} from {existing_order.get_side()} to {side}")
                self.remove_order(name, timestamp, "DIRECTION_SWITCH", candle['close'] if candle else 0)
            else:
                self._logger.warning(f"Order {name} already exists with same direction, not creating a new one.")
                return existing_order
        order = OrderObject(name, instrument, step, trail, side, candle)
        if quantity is not None:
            order.quantity = quantity
        self._orders[name] = order
        self._logger.info(f"Created order {name} with side {side} at {timestamp}")
        self._order_logger.log_entry(order)
        if callable(self._handlers):
            try:
                self._handlers(name=name, order=order, timestamp=timestamp)
            except Exception as cb_err:
                self._logger.error(f"_handlers error: {cb_err}")
        return order

    def remove_order(self, name: str, timestamp: datetime, exit_reason: str, exit_price: float):
        order = self._orders.pop(name, None)
        if order:
            self._logger.info(
                f"Order {name} exited: {exit_reason} | "
                f"Entry: {order.get_entry_price():.2f} | Exit: {exit_price:.2f} | "
                f"Max%: {order.get_max_pct():.2f}% | Min%: {order.get_min_pct():.2f}% | "
                f"Retreat: {order.get_retreat():.2f}% | Duration: {(timestamp - order.get_entry_time()).seconds}s"
            )
            self._order_logger.log_exit(order, exit_reason, exit_price)
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
