from datetime import datetime
from src.core.event_bus.events import CandleGenerated
from src.logger_factory import get_logger



class OrderObject:
    def __init__(self, name, instrument, step, trail, side, candle=None):
        self.logger = get_logger(f"InitOrderObject-{name}")
        self.name = name
        self.instrument = instrument
        self.side = side.upper()  # 'BUY' or 'SELL'
        self.step = step or []          # going with step profits, same as step trail
        self.trail = trail or []        # going with step trail, same as step profits 
        self.current_step_idx = 0
        self.current_step = self.step[0] if self.step else 0.05
        self.current_trail = self.trail[0] if self.trail else 0.03
        self.current_candle: CandleGenerated = candle
        self.ltp = 0
        self.filled_steps = set()  # TODO: maybe not the best way, the idea is to track which steps have been filled
        self.total_quantity = 0  # total quantity filled in this order
        self.lots = 1.0     # total_quantity * lots, used for position sizing
        
        self.logger.debug(f"Creating OrderObject: {name}, Instrument: {instrument}, Side: {side}, Step: {self.step}, Trail: {self.trail}")
        

        # Entry & timestamps - Handle both dict and CandleGenerated objects
        self.entry_price = self._extract_close_price(candle)
        if self.entry_price == 0:
            self.logger.warning(f"Entry price is 0 for order {name}, please check the candle data.")
        self.entry_time = datetime.now()
        self.last_update_time = self.entry_time
        self._timestamp = self.entry_time

        # Price tracking
        self.min_price = self.entry_price if self.entry_price > 0 else 0
        self.max_price = self.entry_price if self.entry_price > 0 else 0
        if(self.min_price == 0 or self.max_price == 0):
            self.logger.warning(f"Min/Max price initialized to 0 for order {name}, please check the entry price.")
        self.logger.debug(f"OrderObject initialized with entry price: {self.entry_price}, min price: {self.min_price}, max price: {self.max_price}")
        self.logger.debug(f"OrderObject {name} created with side {self.side}, entry price {self.entry_price}, step {self.step}, trail {self.trail}")

        # Performance tracking (NEW)
        self.max_pct = 0.0  # highest favorable movement %
        self.min_pct = 0.0  # worst adverse movement %
        self.retreat = 0.0  # pullback from max
        self.current_pct = 0.0  # current PnL %
        self.logger.debug(f"OrderObject {name} initialized with max_pct: {self.max_pct}, min_pct: {self.min_pct}, retreat: {self.retreat}, current_pct: {self.current_pct}")
    
    def _extract_close_price(self, candle):
        """Extract close price from either dict or CandleGenerated object."""
        if not candle:
            return 0
        
        try:
            # Handle CandleGenerated event object
            if hasattr(candle, 'close'):
                return float(candle.close)
            # Handle dictionary format
            elif isinstance(candle, dict) and 'close' in candle:
                return float(candle['close'])
            else:
                self.logger.warning(f"Unrecognized candle format: {type(candle)}")
                return 0
        except (ValueError, TypeError) as e:
            self.logger.error(f"Error extracting close price from candle: {e}")
            return 0

    # ----------------- setters -----------------
    def set_ltp(self, ltp, timestamp=None):
        self.logger.debug(f"Setting LTP for {self.name}: {ltp} at {timestamp}")
        self.ltp = ltp
        
        self._update_min_max_price(ltp)
        self._update_pct_stats()
        self.update_step()
        self.last_update_time = timestamp or datetime.now()
        self._timestamp = self.last_update_time # do we need this ?
        if self.entry_price == 0:
            self.entry_price = ltp
            self.entry_time = self.last_update_time

    ## proof: just set the candle
    def set_current_candle(self, candle, timestamp=None):
        self.current_candle: CandleGenerated = candle
        

    ## proof
    def _update_min_max_price(self, price):
        self.logger.debug(f"Updating min/max price for {self.name}: current price {price}, min price {self.min_price}, max price {self.max_price}") 
        if self.min_price == 0 or price < self.min_price:
            self.min_price = price
        if self.max_price == 0 or price > self.max_price:
            self.max_price = price

    def _update_pct_stats(self):
        self.logger.debug(f"Updating pct stats for {self.name}")
        if not self.entry_price:
            return

        # Current % move
        if self.side == "BUY":
            self.current_pct = ((self.ltp - self.entry_price) / self.entry_price) * 100
            self.max_pct = max(self.max_pct, ((self.max_price - self.entry_price) / self.entry_price) * 100)
            self.min_pct = min(self.min_pct, ((self.min_price - self.entry_price) / self.entry_price) * 100)
            self.retreat = self.max_pct - self.current_pct
        else:  # SELL
            self.current_pct = ((self.entry_price - self.ltp) / self.entry_price) * 100
            self.max_pct = max(self.max_pct, ((self.entry_price - self.min_price) / self.entry_price) * 100)
            self.min_pct = min(self.min_pct, ((self.entry_price - self.max_price) / self.entry_price) * 100)
            self.retreat = self.max_pct - self.current_pct

    # ----------------- getters -----------------
    def get_current_step(self):
        return self.step[self.current_step_idx] if self.step else 0

    def get_current_trail(self):
        return self.trail[self.current_step_idx] if self.trail else 0

    def update_step(self):
        self.logger.debug(f"Updating step for {self.name}: current step idx {self.current_step_idx}, current step {self.current_step}, current trail {self.current_trail}")
        if not self.step or not self.entry_price:
            self.logger.warning(f"Cannot update step for {self.name}: step list or entry price is not set.")
            return
        price_move_pct = ((self.ltp - self.entry_price) / self.entry_price) if self.side == 'BUY' else ((self.entry_price - self.ltp) / self.entry_price)
        for i, s in enumerate(self.step):
            if price_move_pct >= s and i > self.current_step_idx:
                self.current_step_idx = i
                self.current_step = s
                self.current_trail = self.trail[i] if i < len(self.trail) else self.trail[-1]
        print(f"Updated step for {self.name}: current step idx {self.current_step_idx}, current step {self.current_step}, current trail {self.current_trail}")

    # convenience accessors
    def get_entry_price(self): return self.entry_price
    def get_entry_time(self): return self.entry_time
    def get_min_price(self): return self.min_price
    def set_min_price(self, price): self.min_price = price
    def get_max_price(self): return self.max_price
    def set_max_price(self, price): self.max_price = price
    def get_side(self): return self.side
    def get_name(self): return self.name
    def get_instrument(self): return self.instrument
    def get_ltp(self): return self.ltp

    # NEW: insight getters
    def get_max_pct(self): return self.max_pct
    def get_min_pct(self): return self.min_pct
    def get_current_pct(self): return self.current_pct
    def get_retreat(self): return self.retreat
