from typing import Dict, Any
from datetime import datetime
from .base_executor import BaseExecutor


class UpstoxExecutor(BaseExecutor):
    """Upstox-specific order executor."""
    
    def __init__(self, client=None, paper_trade=True, logger=None, config: Dict[str, Any] = None):
        super().__init__(client, paper_trade, logger, config)
        
        # Upstox-specific configuration
        self.exchange = self.config.get('exchange', 'NSE_FO')
        self.product = self.config.get('product', 'I')  # Intraday
        self.validity = self.config.get('validity', 'DAY')
        
        self.logger.info(f"UpstoxExecutor initialized - Exchange: {self.exchange}, Product: {self.product}")
    
    def _place_order_impl(self, symbol: str, side: str, quantity: int, order_type: str = "MARKET") -> Dict[str, Any]:
        """Place order using Upstox API."""
        if not self.client:
            raise RuntimeError("Upstox client not initialized")
        
        # Map our side to Upstox transaction type
        transaction_type = 'BUY' if side == 'BUY' else 'SELL'
        
        order_params = {
            'quantity': quantity,
            'product': self.product,
            'validity': self.validity,
            'price': 0,  # For market orders
            'tag': f"VWAP_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'instrument_token': self._get_instrument_token(symbol),
            'order_type': 'MARKET' if order_type == "MARKET" else 'LIMIT',
            'transaction_type': transaction_type,
            'disclosed_quantity': 0,
            'trigger_price': 0,
            'is_amo': False
        }
        
        # Add price for limit orders
        if order_type == "LIMIT":
            order_params['price'] = self.config.get('limit_price', 0)
        
        self.logger.debug(f"Placing Upstox order with params: {order_params}")
        response = self.client.place_order(**order_params)
        
        return {
            'order_id': response.get('order_id'),
            'status': 'PENDING',
            'price': order_params.get('price', 0),
            'raw_response': response
        }
    
    def _get_order_status_impl(self, order_id: str) -> Dict[str, Any]:
        """Get order status from Upstox."""
        if not self.client:
            raise RuntimeError("Upstox client not initialized")
        
        order_details = self.client.get_order_details(order_id)
        
        if order_details:
            return {
                'order_id': order_id,
                'status': order_details.get('status'),
                'filled_quantity': order_details.get('filled_quantity', 0),
                'pending_quantity': order_details.get('pending_quantity', 0),
                'average_price': order_details.get('average_price', 0),
                'raw_order': order_details
            }
        
        return None
    
    def _cancel_order_impl(self, order_id: str) -> bool:
        """Cancel order in Upstox."""
        if not self.client:
            raise RuntimeError("Upstox client not initialized")
        
        try:
            response = self.client.cancel_order(order_id)
            self.logger.info(f"Upstox order cancelled: {order_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to cancel Upstox order {order_id}: {e}")
            return False
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol for Upstox format."""
        # Upstox has specific symbol formats
        # This is simplified - in practice, you'd need proper symbol mapping
        return symbol.upper()
    
    def _validate_connection(self) -> bool:
        """Validate Upstox connection."""
        if not self.client:
            return False
        
        try:
            # Test connection by getting profile
            profile = self.client.get_profile()
            self.logger.debug(f"Upstox connection validated for user: {profile.get('user_name', 'unknown')}")
            return True
        except Exception as e:
            self.logger.error(f"Upstox connection validation failed: {e}")
            return False
    
    def _get_instrument_token(self, symbol: str) -> str:
        """Get instrument token for symbol."""
        # In practice, you'd have a symbol-to-token mapping
        # This is a placeholder implementation
        instrument_map = self.config.get('instrument_map', {})
        return instrument_map.get(symbol, symbol)
    
    def get_holdings(self) -> Dict[str, Any]:
        """Get holdings from Upstox."""
        if not self.client or self.paper_trade:
            return {}
        
        try:
            holdings = self.client.get_holdings()
            return holdings
        except Exception as e:
            self.logger.error(f"Error fetching Upstox holdings: {e}")
            return {}
    
    def get_funds(self) -> Dict[str, Any]:
        """Get fund information from Upstox."""
        if not self.client or self.paper_trade:
            return {}
        
        try:
            funds = self.client.get_balance()
            return funds
        except Exception as e:
            self.logger.error(f"Error fetching Upstox funds: {e}")
            return {}
