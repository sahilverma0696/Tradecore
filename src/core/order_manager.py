from typing import Dict
from datetime import datetime
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
        
        # Load trading configuration
        self._config_manager = ConfigManager()
        self._trading_config = self._config_manager.get()
        
        self._logger.info("OrderManager initialized")
        
        # Subscribe to trading signal events - CRITICAL for receiving trading signals
        self.subscribe_to_event(EntrySignal, self.on_entry_signal)
        # self.subscribe_to_event(ExitSignal, self.on_exit_signal) ## exit manager is a wired service
        self.subscribe_to_event(QuoteEvent, self._on_ltp_update)
        # self.subscribe_to_event(CandleGenerated, self._on_candle_update)
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
        return self._trading_config.get('exit_steps', [[0.02, 0.3], [0.04, 0.3]])
    
    def _get_quantity_from_config(self, symbol: str = None) -> int:
        """Get quantity from trading config based on symbol or use default."""
        quantities = self._trading_config.get('execution', {}).get('quantities', {})
        
        # Try symbol-specific quantity first
        if symbol:
            symbol_key = symbol.upper()
            if symbol_key in quantities:
                return quantities[symbol_key]
        
        # Fall back to default quantity
        return quantities.get('default', self._trading_config.get('default_quantity', 75))
        
    def _handle_entry_signal(self, event: EntrySignal):
        """Handle entry signal from strategy"""
        print(f"DEBUG: Printing complete event {event}")
        symbol = event.symbol
        side = event.direction
        print(f"DEBUG: Handling entry signal for {symbol} side {side}")

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
        # Create new order
        try:
            order = OrderObject(
                name=symbol,
                instrument=event.symbol,
                step=[s[0] for s in exit_steps], 
                trail=[s[1] for s in exit_steps],
                side=side,
                candle=event.candle
            )
            order.total_quantity = quantity
        except Exception as e:
            print(f"DEBUG: Error creating OrderObject: {e}")
            self._logger.error(f"Error creating OrderObject: {e}")
            

        self._orders[symbol] = order # to be made atomic
        self._logger.info(f"Created order {symbol} {side} @ {event.price} (Qty: {quantity}, Steps: {len(exit_steps)})")
        self._order_logger.log_entry(order)
        
        # Execute order
        for cb in self._handlers:
            try:
                # Send to executioner: symbol, direction, timestamp
                direction = "B" if side == "BUY" else "S"
                cb(event.symbol, direction, getattr(event, 'timestamp', datetime.now()))
            except Exception as e:
                self._logger.error(f"Handler error: {e}")

    def _handle_exit_signal(self, signal_data):
        """Handle exit signal from exit manager"""
        symbol = signal_data['symbol']
        exit_price = signal_data['exit_price']
        exit_reason = signal_data['exit_reason']
        quantity = signal_data.get('quantity', 0)
        
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

    def _on_ltp_update(self, event: QuoteEvent):
        """Handle LTP update events."""
        self.update_ltp(event.instrument, event.ltp, event.timestamp)

    def update_ltp(self, symbol: str, ltp: float, timestamp=None):
        """Update LTP and check for exits"""
        if symbol in self._orders:
            order = self._orders[symbol]
            order.set_ltp(ltp, timestamp)
            
            # Check for exits using exit manager
            if self._exit_manager:
                exit_signal = self._exit_manager.check_exit(order, ltp, timestamp or datetime.now())
                if exit_signal:
                    self._logger.info(f"📉 Exit signal triggered for {symbol}: {exit_signal}")
                    self.handle_signal(exit_signal)

    def update_candle(self, symbol: str, candle: dict, timestamp=None):
        if symbol in self._orders:
            self._orders[symbol].set_current_candle(candle, timestamp)

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
