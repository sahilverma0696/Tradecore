from datetime import datetime
from src.logger_factory import get_logger

class OrderObject:
    def __init__(self, name, instrument, step, trail, side, candle=None):
        self.name = name
        self.instrument = instrument
        self.side = side.upper()  # 'BUY' or 'SELL'
        self.step = step or []
        self.trail = trail or []
        self.current_step_idx = 0
        self.current_step = self.step[0] if self.step else 0.0
        self.current_trail = self.trail[0] if self.trail else 0.0
        self.current_candle = candle
        self.ltp = 0
        self.position_size = 1.0
        self.filled_steps = set()
        self.entry_price = candle['close'] if candle and 'close' in candle else 0
        self.entry_time = datetime.now()
        self.last_update_time = self.entry_time
        self._timestamp = self.entry_time
        self.min_price = self.entry_price if self.entry_price > 0 else 0
        self.max_price = self.entry_price if self.entry_price > 0 else 0
        self.retreat = 0
        self.logger = get_logger(f"OrderObject:{self.name}")

    # ----------------- setters -----------------
    def set_ltp(self, ltp, timestamp=None):
        self.ltp = ltp
        self._update_min_max_price(ltp)
        self.last_update_time = timestamp or datetime.now()
        self._timestamp = self.last_update_time
        if self.entry_price == 0:
            self.entry_price = ltp
            self.entry_time = self.last_update_time

    def set_current_candle(self, candle, timestamp=None):
        self.current_candle = candle
        self.last_update_time = timestamp or datetime.now()
        self._timestamp = self.last_update_time
        if self.entry_price == 0 and candle and 'close' in candle:
            self.entry_price = candle['close']
            self.entry_time = self.last_update_time

    def _update_min_max_price(self, price):
        if self.min_price == 0 or price < self.min_price:
            self.min_price = price
        if self.max_price == 0 or price > self.max_price:
            self.max_price = price

    # ----------------- getters -----------------
    def get_current_step(self):
        return self.step[self.current_step_idx] if self.step else 0

    def get_current_trail(self):
        return self.trail[self.current_step_idx] if self.trail else 0

    def update_step(self):
        if not self.step or not self.entry_price:
            return
        price_move_pct = ((self.ltp - self.entry_price) / self.entry_price) if self.side == 'BUY' else ((self.entry_price - self.ltp) / self.entry_price)
        for i, s in enumerate(self.step):
            if price_move_pct >= s and i > self.current_step_idx:
                self.current_step_idx = i
                self.current_step = s
                self.current_trail = self.trail[i] if i < len(self.trail) else self.trail[-1]

    # convenience accessors
    def get_entry_price(self):
        return self.entry_price
    def get_entry_time(self):
        return self.entry_time
    def get_min_price(self):
        return self.min_price
    def set_min_price(self, price):
        self.min_price = price
    def get_max_price(self):
        return self.max_price
    def set_max_price(self, price):
        self.max_price = price
    def get_side(self):
        return self.side
    def get_name(self):
        return self.name
    def get_instrument(self):
        return self.instrument
    def get_ltp(self):
        return self.ltp
