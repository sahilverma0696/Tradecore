import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from src.core.executors.base_executor import BaseExecutor
from src.core.event_bus import Publisher, OrderExecuted


class MockExecutor(BaseExecutor):
    """Mock executor for paper trading - simulates order execution."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(client=None, paper_trade=True, config=config)
        self.slippage_factor = self.config.get('slippage_factor', 0.0001)
        self.execution_delay = self.config.get('execution_delay', 0.1)
        self.mock_orders = {}
        
        self.logger.info("MockExecutor initialized for paper trading")
    
    def _place_order_impl(self, symbol: str, side: str, quantity: int, order_type: str = "MARKET") -> Dict[str, Any]:
        """Implementation-specific mock order placement."""
        order_id = f"MOCK_{uuid.uuid4().hex[:8].upper()}"
        
        # Simulate execution price with slippage
        base_price = 100.0  # Mock base price
        slippage = base_price * self.slippage_factor
        
        if side.upper() == "BUY":
            execution_price = base_price + slippage
        else:
            execution_price = base_price - slippage
        
        order_data = {
            'order_id': order_id,
            'symbol': symbol,
            'quantity': quantity,
            'side': side.upper(),
            'order_type': order_type,
            'price': execution_price,
            'execution_price': execution_price,
            'status': 'FILLED',
            'timestamp': datetime.now(),
            'exchange': 'MOCK'
        }
        
        self.mock_orders[order_id] = order_data
        
        # Publish OrderExecuted event
        order_executed_event = OrderExecuted(
            timestamp=datetime.now(),
            source=self.__class__.__name__,
            symbol=symbol,
            side=side.upper(),
            price=execution_price,
            quantity=quantity,
            order_id=order_id,
            execution_type="MOCK"
        )
        
        self.publish_event(order_executed_event)
        
        return order_data
    
    def _get_order_status_impl(self, order_id: str) -> Dict[str, Any]:
        """Get mock order status."""
        return self.mock_orders.get(order_id, {})
    
    def _cancel_order_impl(self, order_id: str) -> bool:
        """Cancel mock order."""
        if order_id in self.mock_orders:
            self.mock_orders[order_id]['status'] = 'CANCELLED'
            return True
        return False
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Mock symbol normalization."""
        return symbol.upper()
    
    def _validate_connection(self) -> bool:
        """Mock connection is always valid."""
        return True
    
    def get_positions(self) -> Dict[str, Any]:
        """Calculate mock positions from executed orders."""
        positions = {}
        
        for order in self.mock_orders.values():
            if order['status'] == 'FILLED':
                symbol = order['symbol']
                quantity = order['quantity']
                side = order['side']
                price = order['execution_price']
                
                if symbol not in positions:
                    positions[symbol] = {'quantity': 0, 'avg_price': 0, 'total_cost': 0}
                
                if side == 'BUY':
                    new_cost = positions[symbol]['total_cost'] + (quantity * price)
                    new_quantity = positions[symbol]['quantity'] + quantity
                else:  # SELL
                    new_cost = positions[symbol]['total_cost'] - (quantity * price)
                    new_quantity = positions[symbol]['quantity'] - quantity
                
                positions[symbol]['quantity'] = new_quantity
                positions[symbol]['total_cost'] = new_cost
                
                if new_quantity != 0:
                    positions[symbol]['avg_price'] = new_cost / new_quantity
                else:
                    positions[symbol]['avg_price'] = 0
                    
        return positions
    
    def get_funds(self) -> Dict[str, float]:
        """Get mock fund information."""
        return {
            'available_cash': 100000.0,
            'used_margin': 0.0,
            'available_margin': 100000.0
        }
    
    def is_market_open(self) -> bool:
        """Mock market is always open."""
        return True
    
    def set_slippage_factor(self, factor: float):
        """Set slippage factor for mock execution."""
        self.slippage_factor = factor
        self.config['slippage_factor'] = factor
        self.logger.info(f"Mock slippage factor set to: {factor}")
