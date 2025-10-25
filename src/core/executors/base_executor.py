from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional
import time
from src.logger_factory import get_logger
from src.config_manager import ConfigManager
from src.core.event_bus.mixins import Publisher, Subscriber
from src.core.event_bus.events import OrderEvent




class BaseExecutor(ABC,Publisher, Subscriber):
    """Base class for all order execution implementations."""
    
    def __init__(self, client=None, paper_trade=True, logger=None, config: Dict[str, Any] = None):
        super().__init__()
        self.client = client
        self.paper_trade = paper_trade
        self.logger = get_logger(f"{self.__class__.__name__}")
        self.config = config
        
        # Common configuration
        self.max_retries = self.config.get('max_retries')
        self.retry_delay = self.config.get('retry_delay')
        self.default_quantity = self.config.get('default_quantity')
        
        # Track trades
        self.open_trades = {}
        self.closed_trades = []
        self.total_executed_orders = 0
        
        # subscribe to events 
        self.subscribe_to_event(OrderEvent, self._on_order_event)
        self.logger.info(f"{self.__class__.__name__} initialized - Paper Trade: {self.paper_trade}")
    
    @abstractmethod
    def _on_order_event(self,event: OrderEvent):
        pass
    
    @abstractmethod
    def _place_order_impl(self, symbol: str, side: str, quantity: int, order_type: str = "MARKET") -> Dict[str, Any]:
        """Implementation-specific order placement logic."""
        pass
    
    
    
    @abstractmethod
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol format for the specific broker."""
        pass
    
    
    def execute_order(self, symbol: str, direction: str, timestamp: datetime = None) -> bool:
        """Main order execution method - template pattern."""
        try:
            # Normalize inputs
            normalized_symbol = self._normalize_symbol(symbol)
            side = self._normalize_direction(direction)
            quantity = self.get_quantity(symbol)
            timestamp = timestamp or datetime.now()
            
            self.logger.info(f"Executing order: {side} {quantity} {normalized_symbol}")
            
            # Paper trading mode
            if self.paper_trade:
                return self._execute_paper_trade(normalized_symbol, side, quantity, timestamp)
            
            # Real trading mode
            return self._execute_real_trade(normalized_symbol, side, quantity, timestamp)
            
        except Exception as e:
            self.logger.error(f"Error executing order for {symbol}: {e}")
            return False
    
    def _normalize_direction(self, direction: str) -> str:
        """Normalize direction to standard format."""
        direction = direction.upper()
        if direction in ['B', 'BUY']:
            return 'BUY'
        elif direction in ['S', 'SELL']:
            return 'SELL'
        else:
            raise ValueError(f"Invalid direction: {direction}")
    
    def _execute_paper_trade(self, symbol: str, side: str, quantity: int, timestamp: datetime) -> bool:
        """Execute paper trade (simulation)."""
        fake_order_id = f"PAPER_{int(timestamp.timestamp())}{len(self.open_trades)}"
        
        trade_record = {
            'order_id': fake_order_id,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'timestamp': timestamp,
            'status': 'FILLED',
            'price': 0.0  # Would be filled with current market price
        }
        
        self.open_trades[fake_order_id] = trade_record
        self.total_executed_orders += 1
        
        self.logger.info(f"Paper trade executed: {fake_order_id}")
        return True
    
    def _execute_real_trade(self, symbol: str, side: str, quantity: int, timestamp: datetime) -> bool:
        """Execute real trade with retry logic."""
        if not self._validate_connection():
            self.logger.error("Connection validation failed")
            return False
        
        for attempt in range(self.max_retries):
            try:
                result = self._place_order_impl(symbol, side, quantity)
                
                if result and result.get('order_id'):
                    order_id = result['order_id']
                    
                    trade_record = {
                        'order_id': order_id,
                        'symbol': symbol,
                        'side': side,
                        'quantity': quantity,
                        'timestamp': timestamp,
                        'status': result.get('status', 'PENDING'),
                        'price': result.get('price', 0.0)
                    }
                    
                    self.open_trades[order_id] = trade_record
                    self.total_executed_orders += 1
                    
                    self.logger.info(f"Order placed successfully: {order_id}")
                    return True
                else:
                    self.logger.warning(f"Order placement failed, attempt {attempt + 1}")
                    
            except Exception as e:
                self.logger.error(f"Order placement error (attempt {attempt + 1}): {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        
        self.logger.error(f"Failed to place order after {self.max_retries} attempts")
        return False
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order status."""
        if self.paper_trade:
            return self.open_trades.get(order_id)
        
        try:
            return self._get_order_status_impl(order_id)
        except Exception as e:
            self.logger.error(f"Error getting order status for {order_id}: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if self.paper_trade:
            if order_id in self.open_trades:
                self.open_trades[order_id]['status'] = 'CANCELLED'
                return True
            return False
        
        try:
            return self._cancel_order_impl(order_id)
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    def get_open_trades(self) -> Dict[str, Dict[str, Any]]:
        """Get all open trades."""
        return self.open_trades.copy()
    
    def get_closed_trades(self) -> list:
        """Get all closed trades."""
        return self.closed_trades.copy()
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        return {
            'total_orders': self.total_executed_orders,
            'open_trades': len(self.open_trades),
            'closed_trades': len(self.closed_trades),
            'paper_trade': self.paper_trade
        }
