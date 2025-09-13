from typing import Dict
from datetime import datetime
import json
import os
from src.core.event_bus import Subscriber, Publisher, EntrySignal, ExitSignal, OrderExecuted
from src.core.event_bus.events import CandleGenerated, QuoteEvent
from src.logger_factory import get_logger
from src.core.order_object import OrderObject
from src.core.order_logger import OrderLogger
from src.config_manager import ConfigManager

class OrderManager(Subscriber, Publisher):
    """Manages order lifecycle and execution."""
    
    def __init__(self, log_dir: str = "logs"):
        super().__init__()  # Initialize both mixins
        self._orders: Dict[str, OrderObject] = {}   # symbol -> OrderObject
        self._logger = get_logger("OrderManager")
        self._order_logger = OrderLogger(log_dir)
        self._handlers = []  # callback for order execution
        self._exit_manager = None  # Will be set from main.py
        
        # IPC file for live order data
        self._live_order_file = "data/live_order.json"

        # Load trading configuration
        self._config_manager = ConfigManager()
        self._trading_config = self._config_manager.get()
        
        self._logger.info("OrderManager initialized")
        
        # Subscribe to trading signal events - CRITICAL for receiving trading signals
        self.subscribe_to_event(EntrySignal, self.on_entry_signal)
        # TODO: exit manager directly being called, no need of signal event by bus talking
        # self.subscribe_to_event(ExitSignal, self.on_exit_signal) ## exit manager is a wired service
        
        # this is proof: OrderManager & OrderObject
        self.subscribe_to_event(QuoteEvent, self._on_ltp_update)
        
        self.subscribe_to_event(CandleGenerated, self._handle_update_candle)
        self._logger.info(f"✅ OrderManager subscribed to EntrySignal and ExitSignal events")
        
    def register_handler(self, cb):
        if callable(cb):
            self._logger.debug(f"Registering handler {cb.__name__}")
            self._handlers.append(cb)
    
    def set_exit_manager(self, exit_manager):
        """Set the exit manager for handling exits"""
        self._exit_manager = exit_manager
    
    def _get_exit_steps_from_config(self) -> list:
        """Get exit steps from trading config."""
        return self._trading_config.get('exit_steps')
    
    def _get_quantity_from_config(self, symbol: str = None) -> list:
        """Get quantity array from trading config for a specific symbol."""
        quantities = self._trading_config.get('execution', {}).get('quantities', {})
        return quantities.get(symbol.upper(), quantities.get('default', self._trading_config.get('default_quantity', 75)))

    def _get_trail_from_config(self, symbol: str = None) -> list:
        """Get trail array from trading config"""
        return self._trading_config.get('trails')

    def _write_live_order_data(self):
        """Write current live order data to JSON file for IPC with CLI dashboard."""
        try:
            live_orders = []
            
            for symbol, order in self._orders.items():
                order_data = {
                    "symbol": symbol,
                    "instrument": order.get_instrument(),
                    "side": order.get_side(),
                    "total_quantity": order.get_total_quantity(),
                    "current_quantity": order.get_current_quantity(),
                    "remaining_quantity": order.get_remaining_quantity(),
                    "entry_price": order.get_entry_price(),
                    "current_trail": order.get_current_trail(),
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
            
            with open(self._live_order_file, 'w') as f:
                json.dump(ipc_data, f, indent=2)
            
        except Exception as e:
            self._logger.error(f"Error writing live order data: {e}")

    def _handle_entry_signal(self, event: EntrySignal):
        """Handle entry signal from strategy"""
        symbol = event.symbol
        side = event.direction

        # Check if order already exists
        existing_order = self._orders.get(symbol)
        if existing_order:
            if existing_order.get_side() != side:
                # Close opposite direction order and create new one
                self._logger.info(f"Switching direction for {symbol} from {existing_order.get_side()} to {side}")
                self._exit_order(symbol, event.price, datetime.now(), "DIRECTION_SWITCH")
            else:
                self._logger.warning(f"Order {symbol} already exists with same direction")
                return

        # Get configuration values from trading config
        exit_steps = self._get_exit_steps_from_config()
        quantity = self._get_quantity_from_config(symbol)
        trail_list = self._get_trail_from_config()
        print(type(trail_list))
        # Create new order
        try:
            order = OrderObject(
                name=symbol,
                instrument=event.symbol,
                step=[s[0] for s in exit_steps], 
                trail=trail_list,
                side=side,
                quantity=quantity,
                candle=event.candle
            )
        except Exception as e:
            print(f"DEBUG: Error creating OrderObject: {e}")
            self._logger.error(f"Error creating OrderObject: {e}")
            

        self._orders[symbol] = order # to be made atomic
        self._logger.info(f"Created order {symbol} {side} @ {event.price} (Qty: {quantity}, Steps: {len(exit_steps)})")
        self._order_logger.log_entry(order)
        
        # Update live order IPC file
        self._write_live_order_data()
        
        # Execute order
        for cb in self._handlers:
            try:
                # Send to executioner: symbol, direction, timestamp
                direction = "B" if side == "BUY" else "S"
                cb(event.symbol, direction, getattr(event, 'timestamp', datetime.now()))
            except Exception as e:
                self._logger.error(f"Handler error: {e}")

    def _handle_exit_signal(self, exit_event: ExitSignal):
        """Handle exit signal from exit manager"""
        symbol = exit_event.symbol
        exit_price = exit_event.exit_price
        exit_reason = exit_event.exit_reason
        quantity = exit_event.quantity
        
        self._exit_order(symbol, exit_price, datetime.now(), exit_reason, quantity)

    def _exit_order(self, symbol: str, exit_price: float, timestamp: datetime, exit_reason: str, quantity: int = None):
        """Exit an order and execute the exit trade"""
        order = self._orders.get(symbol)
        if not order:
            return

        # Use full quantity if not specified
        if quantity is None:
            quantity = order.total_quantity

        # Log exit
        self._logger.info(f"Exiting order {symbol}: {exit_reason} @ {exit_price}")
        self._order_logger.log_exit(order, exit_reason, exit_price)
        
        # Execute exit order
        for cb in self._handlers:
            try:
                # Send opposite direction to executioner
                exit_direction = "S" if order.get_side() == "BUY" else "B"
                cb(order.get_instrument(), exit_direction, timestamp)
            except Exception as e:
                self._logger.error(f"Exit handler error: {e}")

        # Remove order if fully exited
        if quantity >= order.total_quantity:
            self._orders.pop(symbol, None)
        
        # Update live order IPC file after exit
        self._write_live_order_data()

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
            order.set_ltp(event.ltp, event.timestamp)

            # Update live order IPC file when LTP changes
            self._write_live_order_data()

            # Check for exits using exit manager
            if self._exit_manager:
                exit_event = self._exit_manager.check_exit(order, event)
                if exit_event:
                    self._logger.info(f"📉 Exit signal triggered for {event.instrument}: {exit_event}")
                    self._handle_exit_signal(exit_event)

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
            self._logger.info(f"📋 Received entry signal for {event.symbol}: {event.direction} at {event.price}")
            print(f"DEBUG: on_entry_signal received for {event.symbol} side {event.direction}")
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
            self._logger.error(f"Error handling exit signal: {e}")
            self._logger.error(f"Error handling exit signal: {e}")
