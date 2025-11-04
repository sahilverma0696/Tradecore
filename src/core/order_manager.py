from typing import Dict, Any
from datetime import datetime
import json
import os
from src.core.event_bus import Subscriber, Publisher, EntrySignal, ExitSignal, OrderExecuted
from src.core.event_bus.events import CandleGenerated, QuoteEvent, OrderEvent
from src.logger_factory import get_logger
from src.core.order_object import OrderObject
from src.core.order_logger import OrderLogger
from src.config_manager import ConfigManager
from src.core.thread_manager import ThreadManager, ThreadPoolType
import src.basic as basic
from src.global_enum import *

class OrderManager(Subscriber, Publisher):
    """Manages order lifecycle and execution."""
    
    def __init__(self, log_dir: str = "logs"):
        super().__init__()  # Initialize both mixins
        
        self._orders: Dict[str, OrderObject] = {}   # symbol -> OrderObject, unique by ID, State
        self._logger = get_logger("OrderManager")
        self._order_logger = OrderLogger(log_dir)
        self._handlers = []  # callback for order execution
        
        # Thread manager for async operations
        self._thread_manager = ThreadManager()
        
        # IPC file for live order data
        self._live_order_file = "data/live_order.json"

        # Load trading configuration
        self._config_manager = ConfigManager()
        self._trading_config = self._config_manager.get()
        
        self._logger.info("OrderManager initialized")
        
        # Subscribe to trading signal events - CRITICAL for receiving trading signals
        self.subscribe_to_event(EntrySignal, self.on_entry_signal)
        
        # this is proof: OrderManager & OrderObject
        self.subscribe_to_event(QuoteEvent, self._on_ltp_update)
        
        self.subscribe_to_event(CandleGenerated, self._handle_update_candle)
        self._logger.info(f"✅ OrderManager subscribed to EntrySignal and ExitSignal events")
        
        self.loss_stop_low = float(self._trading_config.get('loss_stop_low'))
        self.loss_stop_high = float(self._trading_config.get('loss_stop_high'))
      
    # # this way is not in use  
    # def register_handler(self, cb):
    #     if callable(cb):
    #         self._logger.debug(f"Registering handler {cb.__name__}")
    #         self._handlers.append(cb)
    
    
    def _handle_entry_signal(self, event: EntrySignal):
        """Handle entry signal from strategy"""
        symbol = event.symbol
        side = event.direction

        # Check if order already exists
        existing_order = self._orders.get(symbol)
        
        if existing_order and  existing_order.state == ORDERSTATE.OPEN:
            if existing_order.get_side() != side:
                # Closing order in opposite direction
                # EXIT CASE 1 : Direction switch, profit negative
                # this is the only case where an exit signal is generated from entry signal
                self._logger.info(f"Switching direction for {symbol} from {existing_order.get_side()} to {side}")
                self._execute_order(existing_order,type ='SWITCH')
            else:
                self._logger.info(f"Duplicate entry signal, same side for {symbol}, ignoring.")
                return
            
        # Create new order
        try:
            order = OrderObject(
                name=symbol,
                instrument=event.symbol,
                trail=self._trading_config.get('trail'),
                side=side,
                quantity=self._trading_config.get('quantity'),
                candle=event.candle,
                loss_stop_low=self.loss_stop_low,
                loss_stop_high=self.loss_stop_high
            )
            
        except Exception as e:
            self._logger.error(f"ORDER OBJECT CREATION FAIL: {symbol}: {e}")
            return
        
        self._execute_order(order,type="ENTRY")
        self._orders[symbol] = order # ?to be made atomic: no, event based system in market order, system expects liquidity in the market
        self._logger.info(f"Created order {symbol} {side} @ {event.price}")
        self._order_logger.log_entry(order)
        
        # Update live order IPC file
        if order.state == ORDERSTATE.OPEN:
            self._write_live_order_data()
        

    def _execute_order(self, order: OrderObject,type:str):
        
        
        side = order.get_side()
        if type == 'EXIT':
            '''
            This only sends exit signal for change in direction signal, honestly should not be executed since 
            Stop loss should be able to stop it, if there is an event fired from this, it is a problem
            '''
            if order.get_side() == "BUY":
                side = "SELL"
            else:
                side = "BUY"
            order.state = ORDERSTATE.CLOSE
            

        orderEvent = OrderEvent(
            timestamp=order._timestamp,
            order_id=order.id,
            instrument=order.get_instrument(),
            side=side,
            price=order.ltp if order.ltp != 0 else order.const_entry_price,
            strategy="VWAP",
            type=type,
            candle= order.current_candle,
            meta_info='placeholder for now',
            source=self.__class__.__name__
        )
        # execute the side as it is 
        self.publish_event(orderEvent)
        self._cleanup_closed_orders(order.get_instrument())
        
        
        # since this is a an event based system, the sync flow is not expected in functions
        
    def _handle_update_candle(self, event: CandleGenerated):
        """Handle candle update events."""
        if event.symbol in self._orders:
            order = self._orders[event.symbol]
            if order and  order.state == ORDERSTATE.OPEN:
                self.update_candle(event.symbol, event)

    def _on_ltp_update(self, event: QuoteEvent):
        """Handle LTP update events."""
        if event.instrument in self._orders:
            order = self._orders[event.instrument]
            if order and order.state == ORDERSTATE.OPEN:
                self.update_ltp(event)

    def update_ltp(self, event: QuoteEvent):
        """Update LTP and check for exits"""
        if event.instrument in self._orders:
            order = self._orders[event.instrument]
            # OrderObject now handles exit logic internally
            order.set_ltp(event.ltp, event.timestamp)
            
            # Update live order IPC file when LTP changes    
            self._write_live_order_data()


    def update_candle(self, symbol: str, candle: CandleGenerated):
        if symbol in self._orders:
            self._orders[symbol].set_current_candle(candle)

    def has_order(self, symbol: str) -> bool:
        return symbol in self._orders

    def get_order(self, symbol: str):
        return self._orders.get(symbol)

    def all_orders(self):
        return self._orders.values()

    def on_entry_signal(self, event: EntrySignal):
        """Handle entry signal events."""
        try:
            # Process entry signal and place order
            self._handle_entry_signal(event)
            
        except Exception as e:
            self._logger.error(f"Error handling entry signal: {e}")
    
    
    def _write_live_order_data(self):
        """Write current live order data to JSON file for IPC with CLI dashboard."""
        try:
            # Ensure data directory exists
            os.makedirs("data", exist_ok=True)
            
            live_orders = []
            
            for symbol, order in self._orders.items():
                order_data = {
                    "id": order.id,
                    "symbol": symbol,
                    "instrument": order.get_instrument(),
                    "side": order.get_side(),
                    "total_quantity": order.quantity,
                    "entry_price": basic.round4(order.const_entry_price),
                    "net_stop": order.net_zero_stop,
                    "zero_stop": order.zero_stop,
                    "loss_stop": order.loss_stop,
                    "current_ltp": order.ltp,
                    "current_profit_percentage": order.get_current_profit_percentage(),
                    "current_profit": order.get_current_profit(),
                    "trigger": order.trigger * 100,
                    "retreat": order.get_retreat(),
                    "max_move_percentage": order.get_max_move_percentage(),
                    "min_move_percentage": order.get_min_move_percentage(),
                    "entry_time": order.get_entry_time().isoformat() if order.get_entry_time() else None,
                    "last_update": datetime.now().isoformat()
                }
                live_orders.append(order_data)
            
            # Write to IPC file
            ipc_data = {
                "timestamp": datetime.now().isoformat(),
                "total_orders": len(live_orders),
                "orders": live_orders
            }
            
            with open("data/live_order.json", 'w') as f:
                json.dump(ipc_data, f, indent=2)
            
        except Exception as e:
            self._logger.error(f"Error writing live order data: {e}")
            import traceback
            self._logger.error(f"Traceback: {traceback.format_exc()}")
    
    def _cleanup_closed_orders(self,symbol:str):
        """Remove closed order for given symbol."""
        order = self._orders.get(symbol)
        if order and order.state == ORDERSTATE.CLOSE:
            del self._orders[symbol]
            self._logger.info(f"Removed closed order for {symbol} from OrderManager.")
        #TODO: log this order by event bus into order archives

