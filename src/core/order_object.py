from datetime import datetime
from src.core.event_bus.events import CandleGenerated, ExitSignal
from src.core.event_bus.mixins import Publisher
from src.logger_factory import get_logger
from src.core.exit_manager import ExitManager
from typing import Optional, Dict, Any


class OrderObject(Publisher):
    '''
    Data + Logic container, 
    Contains the data 
    Updates the data 
    Has inbuild logic for exit management via ExitManager Event based
    '''
    def __init__(self, name, instrument, trail, side, quantity, candle: CandleGenerated):
        # TODO: implement market close logic: 1337
        # no default values, the system expects to be having values from config
        # else it fails
        
        # basic information
        self.logger = get_logger(f"InitOrderObject-{name}")
        self.const_name = name
        self.const_instrument = instrument
        self.state = "OPEN"
        self.const_side = side.upper()  # 'BUY' or 'SELL'
        

        # information from config and is in steps
        self.quantity = quantity # array of step exit, these are constant values, not percentage
        
        # types of stops
        # profit stop
        self.trigger = trail   # trigger is a single percentage value, which triggers from min || max fall
        # this is entry stop, in case the signal is not promising enough
        self.zero_stop = 0  # to set as the entry price based on side, after 1 minute of entry
        # this is loss stop, in case of direction switch, although at zero_stop should change the side of order so this should not be triggered, if this is triggered there is gap in system
        self.hard_stop = 0  # this is the absolute hard stop, this will be set some percentage away from entry price based on side
        
        # this works as the entry candle: gives the entry price, and then updated with every candle, for monitoring purpose
        # this step will update by confimation from the executor for the market price on which entry actually happened
        self.current_candle: CandleGenerated = candle
        
        self.ltp = 0  # most important guy in the team
                
        # Initialize exit manager as a library
        self.exit_manager = ExitManager(f"ExitManager-{name}")

        
        self.logger.debug(f"Creating OrderObject: {name}, Instrument: {instrument}, Side: {side}, Trail: {self.trigger}, Quantity: {self.step_quantity}")

        # Entry & timestamps
        # entry price can be zero, this is normal
        self.const_entry_price = candle.close
        
        self.const_entry_time = candle.timestamp # this will help in starting the zero_stop timer
        self.last_update_time = self.const_entry_time
        self._timestamp = self.const_entry_time

        # Price tracking
        self.min_price = self.const_entry_price
        self.max_price = self.const_entry_price
        
        # Performance tracking - now calculated via exit manager
        self.max_move_percentage = 0.0
        self.min_move_percentage = 0.0
        self.retreat = 0.0
        self.current_profit_percentage = 0.0
        self.current_profit = 0.0


    def set_ltp(self, ltp, timestamp=None) -> Optional[Dict[str, Any]]:
        """Set LTP and return exit information if exit conditions are met."""
        
        # Update order state
        self.ltp = ltp
        # Check for exit conditions using exit manager
        exit_info = self.exit_manager.check(self)
        if exit_info:
            # create exit signal and send it to executor
            # Send exit signal with opposite side
            opposite_side = "SELL" if self.const_side == "BUY" else "BUY"
            exitEvent = ExitSignal(
                symbol=self.const_name,
                direction=opposite_side,
                price=ltp,
                quantity=self.quantity,
                exit_type=exit_info['exit_type'],
                reason=exit_info['reason']
            )
            self.publish(exitEvent)
            
            # set order state to closed
            self.state = "CLOSED"
            #archive it to be just in order logs for analysis
            # and return 
        else:
            self._update_min_max_price(ltp)
            self._update_performance_metrics()
            self.last_update_time = timestamp or datetime.now()
            self._timestamp = self.last_update_time

        # there is no order state, the real orderObject is checked in the exit manager
        
        # Check for step-based exits if step changed
        # if self.current_step_idx != previous_step_idx:
        #     self.logger.info(f"Step changed for {self.const_name}: {previous_step_idx} → {self.current_step_idx}")
            
        #     if not exit_info:
        #         exit_info = self.exit_manager.check_step_exit(order_state, previous_step_idx)
        
        # return exit_info

    def _get_order_state(self) -> Dict[str, Any]:
        """Get current order state for exit manager."""
        return {
            'name': self.const_name,
            'side': self.const_side,
            'ltp': self.ltp,
            'entry_price': self.const_entry_price,
            'min_price': self.min_price,
            'max_price': self.max_price,
            'current_step_idx': self.current_step_idx,
            'current_trigger': self.current_trigger,
            'quantity': self.step_quantity,
            'step': self.step,
            'current_profit_percentage': self.current_profit_percentage,
            'retreat': self.retreat
        }

    def _update_performance_metrics(self):
        """Update performance metrics using exit manager calculations."""
        order_state = self._get_order_state()
        metrics = self.exit_manager.calculate_performance_metrics(order_state)
        
        # Update instance variables with calculated metrics
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

    def update_step(self):
        if not self.step or not self.const_entry_price:
            self.logger.warning(f"Cannot update step for {self.const_name}: step list or entry price is not set.")
            return
        price_move_pct = ((self.ltp - self.const_entry_price) / self.const_entry_price) if self.const_side == 'BUY' else ((self.const_entry_price - self.ltp) / self.const_entry_price)
        for i, s in enumerate(self.step):
            if price_move_pct >= s and i > self.current_step_idx:
                self.logger.debug(f"Updating step for {self.const_name}: current step idx {self.current_step_idx}, current step {self.current_step}, current trail {self.current_trigger}")
                self.current_step_idx = i
                self.current_step = s

    # Getters - keep existing interface
    def get_current_step(self):
        return self.step[self.current_step_idx] if self.step else 0

    def get_current_trigger(self):
        return self.trigger
    
    def get_current_quantity(self):
        # returns the current step quantity to be exited
        return self.step_quantity[self.current_step_idx]
    
    def get_current_step_idx(self):
        return self.current_step_idx

    def get_current_step_trigger(self):
        return self.step[self.current_step_idx]
    
    
    # ...existing code for all other getters...
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
    def get_max_move_percentage(self): return self.max_move_percentage
    def get_min_move_percentage(self): return self.min_move_percentage
    def get_current_profit_percentage(self): return self.current_profit_percentage
    def get_current_profit(self): return self.current_profit
    def get_retreat(self): return self.retreat
    def get_total_quantity(self): return self.total_quantity
    def get_remaining_quantity(self): return self.total_quantity - self.filled_quantity
