from typing import Dict, Any
from datetime import datetime
from .base_executor import BaseExecutor


class ZerodhaExecutor(BaseExecutor):
    """Zerodha Kite-specific order executor."""
    
    def __init__(self, client=None, paper_trade=True, logger=None, config: Dict[str, Any] = None):
        super().__init__(client, paper_trade, logger, config)
        
        # Zerodha-specific configuration
        self.exchange = self.config.get('exchange', 'NFO')  # NSE Futures & Options
        self.product = self.config.get('product', 'MIS')     # Margin Intraday Squareoff
        self.variety = self.config.get('variety', 'regular')
        
        self.logger.info(f"ZerodhaExecutor initialized - Exchange: {self.exchange}, Product: {self.product}")
    
    def _place_order_impl(self, symbol: str, side: str, quantity: int, order_type: str = "MARKET") -> Dict[str, Any]:
        """Place order using Zerodha Kite API."""
        if not self.client:
            raise RuntimeError("Zerodha client not initialized")
        
        # Map our side to Kite transaction type
        transaction_type = self.client.TRANSACTION_TYPE_BUY if side == 'BUY' else self.client.TRANSACTION_TYPE_SELL
        
        order_params = {
            'variety': self.client.VARIETY_REGULAR,
            'exchange': self._get_exchange_for_symbol(symbol),
            'tradingsymbol': symbol,
            'transaction_type': transaction_type,
            'quantity': quantity,
            'order_type': self.client.ORDER_TYPE_MARKET if order_type == "MARKET" else self.client.ORDER_TYPE_LIMIT,
            'product': self.client.PRODUCT_MIS,
        }
        
        # Add price for limit orders
        if order_type == "LIMIT":
            order_params['price'] = self.config.get('limit_price', 0)
        
        self.logger.debug(f"Placing Zerodha order with params: {order_params}")
        response = self.client.place_order(**order_params)
        
        return {
            'order_id': response.get('order_id'),
            'status': 'PENDING',
            'price': order_params.get('price', 0),
            'raw_response': response
        }
    
    def _get_order_status_impl(self, order_id: str) -> Dict[str, Any]:
        """Get order status from Zerodha."""
        if not self.client:
            raise RuntimeError("Zerodha client not initialized")
        
        orders = self.client.orders()
        for order in orders:
            if order.get('order_id') == order_id:
                return {
                    'order_id': order_id,
                    'status': order.get('status'),
                    'filled_quantity': order.get('filled_quantity', 0),
                    'pending_quantity': order.get('pending_quantity', 0),
                    'average_price': order.get('average_price', 0),
                    'raw_order': order
                }
        
        return None
    
    def _cancel_order_impl(self, order_id: str) -> bool:
        """Cancel order in Zerodha."""
        if not self.client:
            raise RuntimeError("Zerodha client not initialized")
        
        try:
            response = self.client.cancel_order(
                variety=self.client.VARIETY_REGULAR,
                order_id=order_id
            )
            self.logger.info(f"Zerodha order cancelled: {order_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to cancel Zerodha order {order_id}: {e}")
            return False
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol for Zerodha format."""
        # Zerodha uses specific symbol formats for F&O
        # This is a simplified version - in practice, you'd need proper symbol mapping
        return symbol.upper()
    
    def _validate_connection(self) -> bool:
        """Validate Zerodha connection."""
        if not self.client:
            return False
        
        try:
            # Test connection by getting profile
            profile = self.client.profile()
            self.logger.debug(f"Zerodha connection validated for user: {profile.get('user_name', 'unknown')}")
            return True
        except Exception as e:
            self.logger.error(f"Zerodha connection validation failed: {e}")
            return False
    
    def _get_exchange_for_symbol(self, symbol: str) -> str:
        """Get appropriate exchange for symbol."""
        # This is simplified - in practice, you'd have proper symbol-to-exchange mapping
        if 'NIFTY' in symbol or 'BANKNIFTY' in symbol:
            return 'NFO'  # NSE F&O
        elif symbol.endswith('EQ'):
            return 'NSE'  # NSE Equity
        else:
            return self.exchange  # Default exchange
    
    def get_positions(self) -> Dict[str, Any]:
        """Get current positions from Zerodha."""
        if not self.client or self.paper_trade:
            return {}
        
        try:
            positions = self.client.positions()
            return {
                'net_positions': positions.get('net', []),
                'day_positions': positions.get('day', [])
            }
        except Exception as e:
            self.logger.error(f"Error fetching Zerodha positions: {e}")
            return {}
    
    def get_margins(self) -> Dict[str, Any]:
        """Get margin information from Zerodha."""
        if not self.client or self.paper_trade:
            return {}
        
        try:
            margins = self.client.margins()
            return margins
        except Exception as e:
            self.logger.error(f"Error fetching Zerodha margins: {e}")
            return {}
