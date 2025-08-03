from typing import Dict
from datetime import datetime
from src.logger_factory import get_logger
from src.core.order_object import OrderObject
from src.core.order_logger import OrderLogger

class OrderManager:
    """Manages active orders and delegates logging."""

    def __init__(self, log_dir: str = "logs"):
        self._orders: Dict[str, OrderObject] = {}   # symbol -> OrderObject
        self._logger = get_logger("OrderManager")
        self._order_logger = OrderLogger(log_dir)
        self._handlers = []  # callback for order execution
        self._exit_manager = None  # Will be set from main.py
        self._logger.info("OrderManager initialized")
        
    def register_handler(self, cb):
        if callable(cb):
            self._logger.debug(f"Registering handler {cb.__name__}")
            self._handlers.append(cb)
    
    def set_exit_manager(self, exit_manager):
        """Set the exit manager for handling exits"""
        self._exit_manager = exit_manager
        
    def handle_signal(self, signal_data: dict):
        """Handle entry signals from strategy"""
        signal_type = signal_data.get('signal')
        symbol = signal_data.get('symbol')
        
        if signal_type == 'ENTER':
            self._handle_entry_signal(signal_data)
        elif signal_type == 'EXIT':
            self._handle_exit_signal(signal_data)
        else:
            self._logger.warning(f"Unknown signal: {signal_type} for symbol: {symbol}")

    def _handle_entry_signal(self, signal_data):
        """Handle entry signal from strategy"""
        symbol = signal_data['symbol']
        side = signal_data['side']
        
        # Check if order already exists
        existing_order = self._orders.get(symbol)
        if existing_order:
            if existing_order.get_side() != side:
                # Close opposite direction order and create new one
                self._logger.info(f"Switching direction for {symbol} from {existing_order.get_side()} to {side}")
                self._exit_order(symbol, signal_data['entry_price'], datetime.now(), "DIRECTION_SWITCH")
            else:
                self._logger.warning(f"Order {symbol} already exists with same direction")
                return

        # Create new order
        order = OrderObject(
            name=symbol,
            instrument=signal_data['name'],
            step=[s[0] for s in signal_data.get('steps', [])],
            trail=[s[1] for s in signal_data.get('steps', [])],
            side=side,
            candle=signal_data['candle']
        )
        order.total_quantity = signal_data['quantity']
        
        self._orders[symbol] = order
        self._logger.info(f"Created order {symbol} {side} @ {signal_data['entry_price']}")
        self._order_logger.log_entry(order)
        
        # Execute order
        for cb in self._handlers:
            try:
                # Send to executioner: symbol, direction, timestamp
                direction = "B" if side == "BUY" else "S"
                cb(signal_data['name'], direction, signal_data['entry_time'])
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

    def update_ltp(self, symbol: str, ltp: float, timestamp=None):
        """Update LTP and check for exits"""
        if symbol in self._orders:
            order = self._orders[symbol]
            order.set_ltp(ltp, timestamp)
            
            # Check for exits using exit manager
            if self._exit_manager:
                exit_signal = self._exit_manager.check_exit(order, ltp, timestamp or datetime.now())
                if exit_signal:
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
