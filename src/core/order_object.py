from datetime import datetime
from src.core.event_bus.events import CandleGenerated, OrderEvent
from src.core.event_bus.mixins import Publisher
from src.logger_factory import get_logger
from src.core.exit_manager import ExitManager
from typing import Optional, Dict, Any
import time
import src.basic as basic
from src.global_enum import ORDERSTATE


class OrderObject(Publisher):
    """Position state container. Delegates exit logic to ExitManager."""

    def __init__(self, name, instrument, trail, side, quantity, candle: CandleGenerated, loss_stop_low: float, loss_stop_high: float):
        self.logger = get_logger(f"OrderObject-{name}")
        self.id = int(time.time())
        self.const_name = name
        self.const_instrument = instrument
        self.state = ORDERSTATE.OPEN
        self.const_side = side.upper()  # 'BUY' or 'SELL'

        self.quantity = quantity
        self.total_quantity = quantity
        self.filled_quantity = 0
        self.current_step_idx = 0

        self.trigger = trail

        self.const_entry_price = candle.close

        self.zero_stop = 0
        self.zero_stop_state = False

        self.loss_stop_low = loss_stop_low
        self.loss_stop_high = loss_stop_high
        self.loss_stop = basic.round4(self.const_entry_price * (self.loss_stop_low if self.const_side == "BUY" else self.loss_stop_high))

        self.net_zero_stop = 0
        self.net_zero_state = False

        self.current_candle: CandleGenerated = candle

        self.ltp = 0

        self.exit_manager = ExitManager(f"ExitManager-{name}")

        self.logger.debug(f"OrderObject created: {name}  instrument={instrument}  side={side}  trail={self.trigger}")

        self.const_entry_time = candle.timestamp
        self.last_update_time = self.const_entry_time
        self._timestamp = self.const_entry_time

        self.min_price = self.const_entry_price
        self.max_price = self.const_entry_price

        self.max_move_percentage = 0.0
        self.min_move_percentage = 0.0
        self.retreat = 0.0
        self.current_profit_percentage = 0.0
        self.current_profit = 0.0

    def _is_price_bounds(self, percentage: float) -> bool:
        diff = abs(self.ltp - self.const_entry_price)
        return diff > self.const_entry_price * percentage

    def _set_stops(self):
        if not self.zero_stop_state and self._is_price_bounds(0.01):
            self.zero_stop_state = True
            self.zero_stop = self.const_entry_price

        if not self.net_zero_state and self._is_price_bounds(0.03):
            self.net_zero_state = True
            self.net_zero_stop = self.const_entry_price * (0.97 if self.const_side == "BUY" else 1.03)

    def set_ltp(self, ltp, timestamp=None):
        """Set LTP, run exit checks. Returns exit_info dict if triggered, else None."""
        self.ltp = ltp
        self._set_stops()
        exit_info = self.exit_manager.check(self)
        if exit_info:
            self.state = ORDERSTATE.CLOSE
            return exit_info
        self._update_min_max_price(ltp)
        self._update_performance_metrics()
        self.last_update_time = timestamp or datetime.now()
        self._timestamp = self.last_update_time

    def _get_order_state(self) -> Dict[str, Any]:
        return {
            'name': self.const_name,
            'side': self.const_side,
            'ltp': self.ltp,
            'entry_price': self.const_entry_price,
            'min_price': self.min_price,
            'max_price': self.max_price,
            'current_step_idx': self.current_step_idx,
            'current_trigger': self.trigger,
            'quantity': self.quantity,
            'step': self.current_step_idx,
            'current_profit_percentage': self.current_profit_percentage,
            'retreat': self.retreat,
        }

    def _update_performance_metrics(self):
        metrics = self.exit_manager.calculate_performance_metrics(self._get_order_state())
        self.current_profit = metrics['current_profit']
        self.current_profit_percentage = metrics['current_profit_percentage']
        self.max_move_percentage = max(self.max_move_percentage, metrics['max_move_percentage'])
        self.min_move_percentage = min(self.min_move_percentage, metrics['min_move_percentage'])
        self.retreat = metrics['retreat']

    def set_current_candle(self, candle):
        self.current_candle: CandleGenerated = candle

    def _update_min_max_price(self, price):
        if self.min_price == 0 or price < self.min_price:
            self.min_price = price
        if self.max_price == 0 or price > self.max_price:
            self.max_price = price

    def get_current_trigger(self): return self.trigger
    def get_current_step_idx(self): return self.current_step_idx
    def get_current_step(self): return float('inf')
    def get_current_quantity(self): return self.quantity
    def get_entry_price(self): return self.const_entry_price
    def get_entry_time(self): return self.const_entry_time
    def get_min_price(self): return self.min_price
    def set_min_price(self, price): self.min_price = price
    def get_max_price(self): return self.max_price
    def set_max_price(self, price): self.max_price = price
    def get_side(self): return self.const_side
    def get_name(self): return self.const_name
    def get_instrument(self): return self.const_instrument
    def get_ltp(self): return self.ltp
    def get_max_move_percentage(self): return basic.round4(self.max_move_percentage)
    def get_min_move_percentage(self): return basic.round4(self.min_move_percentage)
    def get_current_profit_percentage(self): return basic.round4(self.current_profit_percentage)
    def get_current_profit(self): return basic.round4(self.current_profit)
    def get_retreat(self): return basic.round4(self.retreat)
    def get_total_quantity(self): return self.total_quantity
    def get_remaining_quantity(self): return self.total_quantity - self.filled_quantity
