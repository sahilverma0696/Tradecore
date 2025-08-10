from datetime import datetime
import time
import json
from src.logger_factory import get_logger
from src.config_manager import ConfigManager
from .executors import ExecutorFactory, BaseExecutor

# Legacy Execute class for backward compatibility
class Execute(BaseExecutor):
    """Legacy Execute class - now extends BaseExecutor for backward compatibility."""
    
    def __init__(self, client, paper_trade=True, logger=None, excel_logger=None, expiry=None):
        # Load trading configuration
        try:
            with open('trading_config.json', 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}
        
        # Extract execution config
        execution_config = config.get('execution', {})
        
        super().__init__(
            client=client,
            paper_trade=paper_trade,
            logger=logger,
            config=execution_config
        )
        
        self.config_manager = ConfigManager()
        self.config_manager.register_watcher(self._config_updated)
        
        # Legacy attributes
        self.excel_logger = excel_logger
        self.expiry = expiry
        self.state = None
        self.delta_sell = execution_config.get('delta_sell')
        self.delta_buy = execution_config.get('delta_buy', 0)
        
        # Determine broker type from client
        self.broker_type = self._detect_broker_type(client)
        
        print(f"\nInitializing Execute with configuration:")
        print(f"Paper Trade: {self.paper_trade}")
        print(f"Broker: {self.broker_type}")
        print(f"Delta SELL: {self.delta_sell}")
        print(f"Delta BUY: {self.delta_buy}")
    
    def _detect_broker_type(self, client) -> str:
        """Detect broker type from client class."""
        if client is None:
            return 'unknown'
        
        client_class = client.__class__.__name__.lower()
        
        if 'kite' in client_class:
            return 'zerodha'
        elif 'binance' in client_class:
            return 'binance'
        elif 'upstox' in client_class:
            return 'upstox'
        else:
            return 'unknown'
    
    def _place_order_impl(self, symbol: str, side: str, quantity: int, order_type: str = "MARKET") -> dict:
        """Legacy implementation for Zerodha."""
        if not self.client:
            raise RuntimeError("Client not initialized")
        
        # Legacy Zerodha implementation
        response = self.client.place_order(
            variety=self.client.VARIETY_REGULAR,
            exchange=self.client.EXCHANGE_NFO,
            tradingsymbol=symbol,
            transaction_type=self.client.TRANSACTION_TYPE_BUY if side == "BUY" else self.client.TRANSACTION_TYPE_SELL,
            quantity=quantity,
            order_type=self.client.ORDER_TYPE_MARKET,
            product=self.client.PRODUCT_MIS,
        )
        
        return {
            'order_id': response.get('order_id'),
            'status': 'PENDING',
            'price': 0,
            'raw_response': response
        }
    
    def _get_order_status_impl(self, order_id: str) -> dict:
        """Legacy implementation."""
        if not self.client:
            return None
        
        orders = self.client.orders()
        for order in orders:
            if order.get('order_id') == order_id:
                return order
        return None
    
    def _cancel_order_impl(self, order_id: str) -> bool:
        """Legacy implementation."""
        if not self.client:
            return False
        
        try:
            self.client.cancel_order(
                variety=self.client.VARIETY_REGULAR,
                order_id=order_id
            )
            return True
        except:
            return False
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Legacy symbol normalization."""
        return symbol.upper()
    
    def _validate_connection(self) -> bool:
        """Legacy connection validation."""
        if not self.client:
            return False
        try:
            self.client.profile()
            return True
        except:
            return False
    
    def _config_updated(self, new_config):
        """Handle config updates - legacy method."""
        if 'execution' in new_config:
            execution_config = new_config['execution']
            old_delta_sell = self.delta_sell
            old_delta_buy = self.delta_buy
            
            self.delta_sell = execution_config.get('delta_sell', self.delta_sell)
            self.delta_buy = execution_config.get('delta_buy', self.delta_buy)
            self.max_retries = execution_config.get('max_retries', self.max_retries)
            self.retry_delay = execution_config.get('retry_delay', self.retry_delay)
            
            if old_delta_sell != self.delta_sell or old_delta_buy != self.delta_buy:
                print(f"\nExecute configuration updated:")
                print(f"delta_sell: {old_delta_sell} -> {self.delta_sell}")
                print(f"delta_buy: {old_delta_buy} -> {self.delta_buy}")
                self.logger.debug(f"Execute config updated - delta_sell: {self.delta_sell}, delta_buy: {self.delta_buy}")
    
    def round_hundred(self, value):
        """Round the given value to the nearest hundred."""
        return round(value / 100) * 100
    
    def place_order(self, symbol, action, timestamp=''):
        """Legacy place_order method."""
        # Map legacy action to direction
        direction = "BUY" if action == "B" else "SELL"
        
        if timestamp == '':
            timestamp = datetime.now()
        elif isinstance(timestamp, str):
            timestamp = datetime.now()
        
        return self.execute_order(symbol, direction, timestamp)


# Factory function for creating modern executors
def create_executor(broker: str, client=None, paper_trade=True, config=None) -> BaseExecutor:
    """
    Create an executor for the specified broker.
    
    Args:
        broker: Broker name ('zerodha', 'binance', 'upstox')
        client: Broker-specific client
        paper_trade: Enable paper trading
        config: Broker-specific configuration
    
    Returns:
        BaseExecutor: Configured executor instance
    """
    return ExecutorFactory.create_executor(broker, client, paper_trade, config)
