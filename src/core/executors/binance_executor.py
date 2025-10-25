from typing import Dict, Any
from datetime import datetime
from .base_executor import BaseExecutor
from src.core.event_bus.events import OrderEvent



class BinanceExecutor(BaseExecutor,):
    """Binance-specific order executor."""
    
    def __init__(self, client=None, paper_trade=True, logger=None, config: Dict[str, Any] = None):
        super().__init__(client, paper_trade, logger, config)
        
        # Binance-specific configuration
        self.test_mode = self.config.get('test_mode', True)  # Binance testnet
        self.time_in_force = self.config.get('time_in_force', 'GTC')  # Good Till Cancelled
        
        self.logger.info(f"BinanceExecutor initialized - Test Mode: {self.test_mode}")
    
    def _on_order_event(self, event: OrderEvent):
        self.logger.info(event)
    
    def _place_order_impl(self, symbol: str, side: str, quantity: int, order_type: str = "MARKET") -> Dict[str, Any]:
        """Place order using Binance API."""
        if not self.client:
            raise RuntimeError("Binance client not initialized")
        
        order_params = {
            'symbol': symbol,
            'side': side,
            'type': 'MARKET' if order_type == "MARKET" else 'LIMIT',
            'quantity': quantity,
        }
        
        # Add time in force for limit orders
        if order_type == "LIMIT":
            order_params['timeInForce'] = self.time_in_force
            order_params['price'] = self.config.get('limit_price', 0)
        
        self.logger.debug(f"Placing Binance order with params: {order_params}")
        
        # Use testnet or live API based on configuration
        if self.test_mode:
            response = self.client.create_test_order(**order_params)
        else:
            response = self.client.create_order(**order_params)
        
        return {
            'order_id': response.get('orderId'),
            'status': response.get('status', 'PENDING'),
            'price': response.get('price', 0),
            'raw_response': response
        }
    
    def _get_order_status_impl(self, order_id: str) -> Dict[str, Any]:
        """Get order status from Binance."""
        if not self.client:
            raise RuntimeError("Binance client not initialized")
        
        # For Binance, we need symbol to get order status
        # This is a limitation - in practice, you'd store symbol with order_id
        symbol = self._get_symbol_for_order(order_id)
        if not symbol:
            return None
        
        order = self.client.get_order(symbol=symbol, orderId=order_id)
        
        return {
            'order_id': order_id,
            'status': order.get('status'),
            'filled_quantity': float(order.get('executedQty', 0)),
            'pending_quantity': float(order.get('origQty', 0)) - float(order.get('executedQty', 0)),
            'average_price': float(order.get('avgPrice', 0)),
            'raw_order': order
        }
    
    def _cancel_order_impl(self, order_id: str) -> bool:
        """Cancel order in Binance."""
        if not self.client:
            raise RuntimeError("Binance client not initialized")
        
        try:
            symbol = self._get_symbol_for_order(order_id)
            if not symbol:
                return False
            
            response = self.client.cancel_order(symbol=symbol, orderId=order_id)
            self.logger.info(f"Binance order cancelled: {order_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to cancel Binance order {order_id}: {e}")
            return False
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol for Binance format."""
        # Binance uses symbols like BTCUSDT, ETHUSDT
        symbol = symbol.upper().replace('/', '').replace('-', '')
        
        # Add USDT if not present (for crypto pairs)
        if not any(symbol.endswith(quote) for quote in ['USDT', 'BTC', 'ETH', 'BNB']):
            symbol += 'USDT'
        
        return symbol
    
    def _validate_connection(self) -> bool:
        """Validate Binance connection."""
        if not self.client:
            return False
        
        try:
            # Test connection by getting account info
            account = self.client.get_account()
            self.logger.debug(f"Binance connection validated for account: {account.get('accountType', 'unknown')}")
            return True
        except Exception as e:
            self.logger.error(f"Binance connection validation failed: {e}")
            return False
    
    def _get_symbol_for_order(self, order_id: str) -> str:
        """Get symbol for order ID - would need proper implementation."""
        # In practice, you'd need to store order_id -> symbol mapping
        # or get from order history
        if order_id in self.open_trades:
            return self.open_trades[order_id]['symbol']
        return None
    
    