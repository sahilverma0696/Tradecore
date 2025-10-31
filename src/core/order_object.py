from datetime import datetime
from src.core.event_bus.events import CandleGenerated, ExitSignal
from src.core.event_bus.mixins import Publisher
from src.logger_factory import get_logger
from src.core.exit_manager import ExitManager
from typing import Optional, Dict, Any
import time
import src.basic as basic
from src.global_enum import *

class OrderObject(Publisher):
    '''
    Data + Logic container, 
    Contains the data 
    Updates the data 
    Has inbuild logic for exit management via ExitManager Event based ( stop loss in here )
    '''
    def __init__(self, name, instrument, trail, side, quantity, candle: CandleGenerated):
        # no default values, the system expects to be having values from config
        # else it fails
        
        
        # basic information
        self.logger = get_logger(f"OrderObject-{name}")
        self.id = int(time.time()) # unique id for each order, helps in ignoring redundant signals
        self.const_name = name
        self.const_instrument = instrument
        self.state = ORDERSTATE.OPEN
        self.const_side = side.upper()  # 'BUY' or 'SELL'
        

        # information from config and is in steps
        self.quantity = quantity # array of step exit, these are constant values, not percentage
        
        # types of stops
        # profit stop
        self.trigger = trail   # trigger is a single percentage value in decimal ?, which triggers from min || max fall
        
        # entry price can be zero, this is normal
        self.const_entry_price = candle.close
        
        #TODO: future release 
        # profite stop, this will be triigered on some profit such that, trading fee is saved atleast 
        # this is entry stop, in case the signal is not promising enough
        self.zero_stop = 0  # to set as the entry price based on side, after 1 minute of entry
        self.zero_stop_state = False
        
        #TODO: read from trading config, very important 
        # this is loss stop, in case of direction switch, although at zero_stop should change the side of order so this should not be triggered, if this is triggered there is gap in system
        self.loss_stop_low = float(self._trading_config.get('loss_stop_low'))
        self.loss_stop_high = float(self._trading_config.get('loss_stop_high'))
        self.loss_stop = basic.round4(self.const_entry_price * (self.loss_stop_low if side == "BUY" else self.loss_stop_high))

        
        # net zero stop, to be set such that no loss happens
        self.net_zero_stop = 0
        self.net_zero_state = False
        
        # this works as the entry candle: gives the entry price, and then updated with every candle, for monitoring purpose
        # this step will update by confimation from the executor for the market price on which entry actually happened
        self.current_candle: CandleGenerated = candle
        
        self.ltp = 0  # most important guy in the team
                
        # Initialize exit manager as a library
        self.exit_manager = ExitManager(f"ExitManager-{name}")

        
        self.logger.debug(f"Creating OrderObject: {name}, Instrument: {instrument}, Side: {side}, Trail: {self.trigger}")

        # Entry & timestamps

        
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
        
    def _is_price_bounds(self,percentage: float) -> bool:
        """Fast check if LTP is outside ±pct% of market_price."""
        diff = abs(self.ltp - self.const_entry_price)
        return diff > self.const_entry_price * percentage

    def _set_stops(self):
        '''
        Checks and sets the stops, such that they can be checked and triggered in exit manager
        '''
        if self.zero_stop_state == False and self._is_price_bounds(0.01):
            self.zero_stop_state = True
            self.zero_stop = self.const_entry_price
            
        if self.net_zero_state == False and self._is_price_bounds(0.03):
            self.net_zero_state = True
            self.net_zero_stop = self.const_entry_price * (0.97 if self.side == "BUY" else 1.03)

        

    def set_ltp(self, ltp, timestamp=None):
        """Set LTP and sends exit event if exit conditions are met."""
        
        # Update order state
        self.ltp = ltp
        self._set_stops()
        # Check for exit conditions using exit manager
        exit_info = self.exit_manager.check(self)
        if exit_info:
            self.state = ORDERSTATE.CLOSE

        else:
            self._update_min_max_price(ltp)
            self._update_performance_metrics()
            self.last_update_time = timestamp or datetime.now()
            self._timestamp = self.last_update_time


    def _get_order_state(self) -> Dict[str, Any]:
        """Get current order state for exit manager."""
        return {
            'name': self.const_name,
            'side': self.const_side,
            'ltp': self.ltp,
            'entry_price': self.const_entry_price,
            'min_price': self.min_price,
            'max_price': self.max_price,
            'current_step_idx': 0,
            'current_trigger': self.trigger,
            'quantity': self.quantity,
            'step': 0,
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


    def get_current_trigger(self):
        return self.trigger
    
    
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
    def get_max_move_percentage(self): return basic.round4(self.max_move_percentage)
    def get_min_move_percentage(self): return basic.round4(self.min_move_percentage)
    def get_current_profit_percentage(self): return basic.round4(self.current_profit_percentage)
    def get_current_profit(self): return basic.round4(self.current_profit)
    def get_retreat(self): return basic.round4(self.retreat)
    def get_total_quantity(self): return self.total_quantity
    def get_remaining_quantity(self): return self.total_quantity - self.filled_quantity
