from datetime import datetime
from logger_factory import get_logger

class OrderObject:
    def __init__(self, name, instrument, step, trail, side, candle=None):
        self.name = name
        self.instrument = instrument
        self.side = side.upper()  # 'BUY' or 'SELL'
        
        # Store step and trail values from config
        self.step = step or []
        self.trail = trail or []
        
        # Initialize tracking variables
        self.current_step_idx = 0  # Track current step index
        self.current_step = self.step[0] if self.step else 0.0
        self.current_trail = self.trail[0] if self.trail else 0.0
        
        self.current_candle = candle
        self.ltp = 0
        self.position_size = 1.0  # Track position size (1.0 = 100%)
        self.filled_steps = set()  # Track which steps have been executed
        
        # Initialize entry price from candle
        if candle and 'close' in candle:
            self.entry_price = candle['close']
        else:
            self.entry_price = 0
            
        # Initialize timestamps
        self.entry_time = datetime.now()
        self.last_update_time = self.entry_time
        self._timestamp = self.entry_time

        self.min_price = self.entry_price if self.entry_price > 0 else 0
        self.max_price = self.entry_price if self.entry_price > 0 else 0
        self.retreat = 0

        self.logger = get_logger(f"OrderObject:{self.name}")
        self.logger.info(f"Initialized OrderObject for {self.name} [{self.side}]")

    # ----------------- SETTERS -----------------
    def set_ltp(self, ltp, timestamp=None):
        """
        Update the last traded price and track entry if this is the first LTP
        
        Args:
            ltp (float): Last traded price
            timestamp (datetime, optional): Timestamp of the LTP update
        """
        self.ltp = ltp
        self._update_min_max_price(ltp)
        self.last_update_time = timestamp or datetime.now()
        self._timestamp = self.last_update_time
        self.logger.debug(f"LTP updated to {ltp} for {self.name}")
        
        # If this is the first time setting LTP and we don't have an entry price yet
        if self.entry_price == 0:
            self.entry_price = ltp
            self.entry_time = self.last_update_time
            self.logger.info(f"Entry price set to {ltp} for {self.name}")

    def set_current_candle(self, candle, timestamp=None):
        """
        Update the current candle and set entry price if not already set
        
        Args:
            candle (dict): Current candle data
            timestamp (datetime, optional): Timestamp of the candle
        """
        self.current_candle = candle
        self.last_update_time = timestamp or datetime.now()
        self._timestamp = self.last_update_time
        self.logger.debug(f"Set new candle for {self.name}: {candle}")
        
        # If we don't have an entry price yet and we have a candle with close price
        if self.entry_price == 0 and candle and 'close' in candle:
            self.entry_price = candle['close']
            self.entry_time = datetime.now()
            self.logger.info(f"Entry price set from candle close: {self.entry_price} for {self.name}")

    def _update_min_max_price(self, price):
        updated = False
        if self.min_price == 0 or price < self.min_price:
            self.min_price = price
            updated = True
        if self.max_price == 0 or price > self.max_price:
            self.max_price = price
            updated = True
        if updated:
            self.logger.debug(f"Updated price range for {self.name}: min={self.min_price}, max={self.max_price}")
            
    # ----------------- GETTERS -----------------
    def get_name(self):
        return self.name
        
    def get_instrument(self):
        return self.instrument
        
    def get_side(self):
        return self.side
        
    def get_ltp(self):
        return self.ltp
        
    def get_step(self):
        try:
            # Ensure current_step is an integer and within bounds
            if not self.step or not len(self.step):
                return 0
            current_step = int(self.current_step)
            if current_step < 0 or current_step >= len(self.step):
                return 0
            return self.step[current_step]
        except (TypeError, IndexError, ValueError) as e:
            self.logger.error(f"Error getting step: {e}. step={self.step}, current_step={self.current_step}")
            return 0
        
    def get_trail(self):
        try:
            # Ensure current_trail is an integer and within bounds
            if not self.trail or not len(self.trail):
                return 0
            current_trail = int(self.current_trail)
            if current_trail < 0 or current_trail >= len(self.trail):
                return 0
            return self.trail[current_trail]
        except (TypeError, IndexError, ValueError) as e:
            self.logger.error(f"Error getting trail: {e}. trail={self.trail}, current_trail={self.current_trail}")
            return 0
        
    def get_current_candle(self):
        return self.current_candle
        
    def get_entry_price(self):
        return self.entry_price
        
    def get_entry_time(self):
        return self.entry_time
        
    def get_min_price(self):
        return self.min_price
        
    def get_max_price(self):
        return self.max_price

    # ----------------- EXIT CONDITIONS -----------------
    def should_exit(self):
        """
        Check if the order should be exited based on current market conditions
        
        Returns:
            tuple: (should_exit: bool, exit_reason: str, exit_price: float)
        """
        if not self.current_candle or not self.ltp:
            return False, None, None
            
        candle = self.current_candle
        exit_price = None
        exit_reason = None
        
        # 1. Update step and trail based on price movement first
        self._update_step_and_trail()
        
        # 2. Update min/max prices and retreat level
        if self.side == 'BUY':
            self.max_price = max(self.max_price, self.ltp)
            self.retreat = self.max_price * (1 - self.current_trail)
            
            # Check for trailing stop exit
            if self.ltp <= self.retreat and self.current_step > 0:
                exit_price = self.retreat
                exit_reason = 'TRAIL'
                self.logger.info(f"Exit signal: {exit_reason} - LTP {self.ltp} hit trail at {self.retreat:.2f}")
                return True, exit_reason, exit_price
                
        else:  # SELL
            self.min_price = min(self.min_price, self.ltp) if self.min_price > 0 else self.ltp
            self.retreat = self.min_price * (1 + self.current_trail)
            
            # Check for trailing stop exit
            if self.ltp >= self.retreat and self.current_step > 0:
                exit_price = self.retreat
                exit_reason = 'TRAIL'
                self.logger.info(f"Exit signal: {exit_reason} - LTP {self.ltp} hit trail at {self.retreat:.2f}")
                return True, exit_reason, exit_price
        
        # 3. Check for VWAP risk exit (only in early stages)
        if 'vwap' in candle and candle['vwap'] and self.current_step_idx == 0:
            if (self.side == 'BUY' and self.ltp < candle['vwap']) or \
               (self.side == 'SELL' and self.ltp > candle['vwap']):
                exit_price = self.ltp
                exit_reason = 'RISK'
                self.logger.info(f"Exit signal: {exit_reason} - LTP {self.ltp} vs VWAP {candle['vwap']:.2f}")
                return True, exit_reason, exit_price
        
        return False, None, None
        
    def _update_step_and_trail(self):
        """Update current step and trail based on price movement"""
        if not self.step or not self.trail or not self.current_candle or not self.entry_price:
            return
            
        # Calculate price movement from entry
        if self.side == 'BUY':
            price_move_pct = (self.ltp - self.entry_price) / self.entry_price
        else:  # SELL
            price_move_pct = (self.entry_price - self.ltp) / self.entry_price
        
        # Find the highest step level we've reached
        new_step_idx = -1
        for i, step_pct in enumerate(self.step):
            if price_move_pct >= step_pct and i < len(self.trail):
                new_step_idx = i
        
        # If we've reached a new step level
        if new_step_idx > self.current_step_idx:
            self.current_step_idx = new_step_idx
            self.current_step = self.step[new_step_idx]
            self.current_trail = self.trail[new_step_idx] if new_step_idx < len(self.trail) else self.trail[-1]
            self.logger.info(
                f"Step reached: {self.current_step*100:.1f}%, "
                f"Trail updated to: {self.current_trail*100:.1f}%"
            )
        
        # Update trail price based on current max/min price and current trail percentage
        if self.side == 'BUY':
            # For buy orders, trail below the highest price seen
            self.retreat = self.max_price * (1 - self.current_trail)
            self.logger.debug(
                f"BUY - LTP: {self.ltp:.2f}, "
                f"Max: {self.max_price:.2f}, "
                f"Trail%: {self.current_trail*100:.2f}%, "
                f"Exit At: {self.retreat:.2f}"
            )
        else:  # SELL
            # For sell orders, trail above the lowest price seen
            self.retreat = self.min_price * (1 + self.current_trail)
            self.logger.debug(
                f"SELL - LTP: {self.ltp:.2f}, "
                f"Min: {self.min_price:.2f}, "
                f"Trail%: {self.current_trail*100:.2f}%, "
                f"Exit At: {self.retreat:.2f}"
            )

    # ----------------- GETTERS -----------------
    def get_ltp(self):
        return self.ltp

    def get_current_step(self):
        return self.current_step

    def get_current_trail(self):
        return self.current_trail

    def get_retreat_price(self):
        return self.retreat

    def get_price_range(self):
        return self.min_price, self.max_price

    def get_name(self):
        return self.name

    def get_instrument(self):
        return self.instrument

    def get_side(self):
        return self.side

    def get_current_candle(self):
        return self.current_candle

    # ----------------- DEBUG / STATE -----------------
    def as_dict(self):
        state = {
            "name": self.name,
            "instrument": self.instrument,
            "side": self.side,
            "step": self.step,
            "trail": self.trail,
            "current_step": self.current_step,
            "current_trail": self.current_trail,
            "ltp": self.ltp,
            "min_price": self.min_price,
            "max_price": self.max_price,
            "retreat": self.retreat
        }
        self.logger.debug(f"Order state dump: {state}")
        return state
    
    def get_max_price(self):
        return self.max_price

    def set_max_price(self, price):
        self.max_price = price
        self.logger.debug(f"Max price updated to {price} for {self.name}")
    
    def get_min_price(self):
        return self.min_price
    
    def set_min_price(self, price):
        self.min_price = price
        self.logger.debug(f"Min price updated to {price} for {self.name}")
    
    def get_entry_price(self):
        # Use open price of entry candle
        if self.current_candle:
            return self.current_candle['open']
        return None
        
    def get_timestamp(self):
        """Get the most recent timestamp for this order"""
        return self._timestamp



# order = OrderObject(
#     name="NIFTY 27000 CE 26 JUN 25",
#     instrument="NSE_FO|50969",
#     step=[0.1, 0.2, 0.3, 0.4, 0.5],
#     trail=[0.03, 0.05, 0.07, 0.1, 0.12],
#     side="BUY"
# )

# # Simulate updates
# order.set_current_candle({'open': 100})
# order.set_ltp(112)
# order.update_step()
# order.update_trail()

# print(order.as_dict())
