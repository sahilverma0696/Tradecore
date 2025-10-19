from typing import Dict, Any
from datetime import datetime
import json
import os
from src.core.event_bus import Subscriber, Publisher, EntrySignal, ExitSignal, OrderExecuted
from src.core.event_bus.events import CandleGenerated, QuoteEvent
from src.logger_factory import get_logger
from src.core.order_object import OrderObject
from src.core.order_logger import OrderLogger
from src.config_manager import ConfigManager
from src.core.thread_manager import ThreadManager, ThreadPoolType

class OrderManager(Subscriber, Publisher):
    """Manages order lifecycle and execution."""
    
    def __init__(self, log_dir: str = "logs"):
        super().__init__()  # Initialize both mixins
        
        # the main dict of all orders
        # TODO: able to move the closed orders to archive, logging benefit
        self._orders: Dict[str, OrderObject] = {}   # symbol -> OrderObject
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
        
    def register_handler(self, cb):
        if callable(cb):
            self._logger.debug(f"Registering handler {cb.__name__}")
            self._handlers.append(cb)
    

    # TODO: maybe this can shift inside the order object, and send signal from there to update the order itself to IPC
    def _write_live_order_data(self):
        """Write current live order data to JSON file for IPC with CLI dashboard."""
        try:
            # Ensure data directory exists
            os.makedirs("data", exist_ok=True)
            
            live_orders = []
            
            for symbol, order in self._orders.items():
                order_data = {
                    "symbol": symbol,
                    "instrument": order.get_instrument(),
                    "side": order.get_side(),
                    "total_quantity": order.quantity,
                    "current_quantity": order.quantity,
                    "remaining_quantity": order.quantity,
                    "entry_price": order.get_entry_price(),
                    "current_trail": 0,
                    "current_ltp": order.get_ltp(),
                    "current_profit_percentage": order.get_current_profit_percentage(),
                    "current_profit": order.get_current_profit(),
                    "retreat": order.get_retreat(),
                    "max_move_percentage": order.get_max_move_percentage(),
                    "min_move_percentage": order.get_min_move_percentage(),
                    "entry_time": order.get_entry_time().isoformat() if order.get_entry_time() else None,
                    "last_update": datetime.now().isoformat(),
                    "status": "ACTIVE",
                    "exit_steps": order.step if hasattr(order, 'step') else [],
                    "trail_steps": order.trail if hasattr(order, 'trail') else []
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

    def _handle_entry_signal(self, event: EntrySignal):
        """Handle entry signal from strategy"""
        symbol = event.symbol
        side = event.direction

        # Check if order already exists
        existing_order = self._orders.get(symbol)
        if existing_order:
            if existing_order.get_side() != side:
                # Closing order in opposite direction
                # EXIT CASE 1 : Direction switch, profit negative
                # this is the only case where an exit signal is generated from entry signal
                self._logger.info(f"Switching direction for {symbol} from {existing_order.get_side()} to {side}")
                self._execute_order(existing_order,type ='EXIT')
            else:
                #TODO FUTURE: this info for same side can be used to add boost logic or exit logic
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
                candle=event.candle
            )
            
        except Exception as e:
            print(f"ORDER OBJECT CREATION FAIL: {symbol}: {e}")
            self._logger.error(f"ORDER OBJECT CREATION FAIL: {symbol}: {e}")
            return

        #TODO: Send this order object to executioner
        
        self._execute_order(order,type="ENTRY")
        self._orders[symbol] = order # ?to be made atomic: no, event based system in market order, system expects liquidity in the market
        self._logger.info(f"Created order {symbol} {side} @ {event.price}")
        self._order_logger.log_entry(order)
        
        # Update live order IPC file
        self._write_live_order_data()
        

    def _handle_exit_signal_from_dict(self, exit_info: Dict[str, Any]):
        """Handle exit signal from OrderObject exit information."""
        symbol = exit_info['symbol']
        exit_price = exit_info['exit_price']
        exit_reason = exit_info['exit_reason']
        quantity = exit_info['quantity']
        
        self._exit_order(symbol, exit_price, datetime.now(), exit_reason, quantity)

    def _execute_order(self, order: OrderExecuted,type:str):
        """
        For cases when we need to send 
        """
        if type == 'EXIT':
            #reverse the side and make event
            pass
        elif type == 'ENTRY':
            # execute the side as it is 
            pass
        #TODO: send execute event to exectuner
        #TODO: mark this order as closed, archive it
        
        # since this is a an event based system, the sync flow is not expected in functions
    def _handle_update_candle(self, event: CandleGenerated):
        """Handle candle update events."""
        if event.symbol in self._orders:
            self.update_candle(event.symbol, event)

    def _on_ltp_update(self, event: QuoteEvent):
        """Handle LTP update events."""
        if event.instrument in self._orders:
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
    
    def on_exit_signal(self, event: ExitSignal):
        """Handle exit signal events."""
        try:
            self._logger.info(f"📋 Received exit signal for {event.symbol}: {event.direction} at {event.price}")
            
            # Process exit signal and close position
            self.handle_exit_signal(event)
            
        except Exception as e:
            self._logger.error(f"Error handling exit signal: {e}")
        try:
            # self._logger.info(f"📋 Received entry signal for {event.symbol}: {event.direction} at {event.price}")
            # print(f"DEBUG: on_entry_signal received for {event.symbol} side {event.direction}")
            # Process entry signal and place order
            self._handle_entry_signal(event)
            
        except Exception as e:
            self._logger.error(f"Error handling entry signal: {e}")
