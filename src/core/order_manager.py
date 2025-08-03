from typing import Dict
from datetime import datetime
from src.logger_factory import get_logger
from src.core.order_object import OrderObject
from src.core.order_logger import OrderLogger
import traceback

class OrderManager:
    """Manages active orders and delegates logging."""

    def __init__(self, log_dir: str = "logs"):
        self._orders: Dict[str, OrderObject] = {}
        self._logger = get_logger("OrderManager")
        self._order_logger = OrderLogger(log_dir)
        self._handlers = []  # callback(name, order, timestamp)
        self._exit_manager = None  # Will be set via register_exit_manager
        self._logger.info("OrderManager initialized")
        
    def register_handler(self, cb):
        if callable(cb):
            self._logger.debug(f"Registering handler {cb.__name__}")
            self._handlers.append(cb)
    
    def register_exit_manager(self, exit_manager):
        """Register exit manager for exit analysis"""
        self._exit_manager = exit_manager
        self._logger.info("Exit manager registered with OrderManager")

    def get_signal(self, signal: str, instrument: str, **kwargs):
        """
        Handles entry and exit signals from strategy and exit manager.
        signal: "ENTER" or "EXIT"
        instrument: symbol/instrument name
        kwargs: additional data (candle, side, step, trail, quantity, timestamp, exit_reason, exit_price)
        """
        if signal == "ENTER":
            self._logger.info(f"Received ENTER signal for instrument: {instrument}")
            candle = kwargs.get('candle')
            side = kwargs.get('side')
            step = kwargs.get('step')
            trail = kwargs.get('trail')
            quantity = kwargs.get('quantity')
            timestamp = kwargs.get('timestamp', datetime.now())
            self.create_order(
                timestamp=timestamp,
                name=instrument,
                instrument=instrument,
                step=step,
                trail=trail,
                side=side,
                candle=candle,
                quantity=quantity
            )
        elif signal == "EXIT":
            self._logger.info(f"Received EXIT signal for instrument: {instrument}")
            timestamp = kwargs.get('timestamp', datetime.now())
            exit_reason = kwargs.get('exit_reason', 'MANUAL')
            exit_price = kwargs.get('exit_price', 0)
            self.remove_order(
                name=instrument,
                timestamp=timestamp,
                exit_reason=exit_reason,
                exit_price=exit_price
            )
        else:
            self._logger.warning(f"Unknown signal: {signal} for instrument: {instrument}")
            return None

    # ------------------------------------------------------------------
    ## TODO: correct this, this is an internal method, not public API, this creates an order, and keeps it in memory
    def create_order(self, timestamp: datetime, name: str, instrument: str, step, trail, side: str, candle=None, quantity=None):
        # Ensure only one direction per instrument
        existing_order = self._orders.get(name)
        if existing_order:
            if existing_order.get_side() != side:
                # Remove existing order before new direction
                self._logger.info(f"Switching direction for order {name} from {existing_order.get_side()} to {side}")
                opposite_order = self.remove_order(name, timestamp, "DIRECTION_SWITCH", candle['close'] if candle else 0)
                if opposite_order:
                    # Execute exit order for opposite direction
                    for cb in self._handlers:
                        try:
                            cb(name, opposite_order, 'EXIT')
                        except Exception as cb_err:
                            self._logger.error(f"Handler error on exit: {cb_err}\n{traceback.format_exc()}")
            else:
                self._logger.warning(f"Order {name} already exists with same direction, not creating a new one.")
                return existing_order
                
        order = OrderObject(name, instrument, step, trail, side, candle)
        if quantity is not None:
            order.quantity = quantity
        self._orders[name] = order
        self._logger.info(f"Created order {name} with side {side} at {timestamp}")
        self._order_logger.log_entry(order)
        
        # Execute entry order
        for cb in self._handlers:
            try:
                cb(name, order, 'ENTRY')
            except Exception as cb_err:
                self._logger.error(f"Handler error on entry: {cb_err}\n{traceback.format_exc()}")
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
            order = self._orders[name]
            order.set_ltp(ltp, timestamp)
            
            # Check for exit signals via exit manager
            if self._exit_manager:
                try:
                    self._exit_manager.check_exit(order, timestamp)
                except Exception as e:
                    self._logger.error(f"Error in exit manager check: {e}\n{traceback.format_exc()}")

    def update_candle(self, name: str, candle: dict, timestamp=None):
        if name in self._orders:
            self._orders[name].set_current_candle(candle, timestamp)

    # Helper to iterate
    def all_orders(self):
        return self._orders.values()
