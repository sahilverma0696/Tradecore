from datetime import datetime
import time
import json
from src.logger_factory import get_logger
from src.config_manager import ConfigManager

class Execute:
    def __init__(self, logger, excel_logger, expiry, client):
        self.config_manager = ConfigManager()
        self.config_manager.register_watcher(self._config_updated)
        
        # Load trading configuration
        with open('trading_config.json', 'r') as f:
            self.config = json.load(f)
        
        # Get execution config
        self.execution_config = self.config['execution']
        self.delta1 = self.execution_config['delta1']
        self.delta2 = self.execution_config['delta2']
        self.max_retries = self.execution_config.get('max_retries', 3)
        self.retry_delay = self.execution_config.get('retry_delay', 1)
        
        self.logger = logger  # An instance of Logger to log messages
        self.excel_logger = excel_logger  # An instance of ExcelTradeLogger for logging trades
        self.expiry = expiry  # Expiry date for options
        self.state = None  # Track current trade direction ('long' or 'short')
        self.open_trades = {}  # Dictionary to store open trades with entry prices and timestamps
        self.closed_trades = []  # List to store last closed positions
        self.client = client

        print(f"\nInitializing Execute with configuration:")
        print(f"Delta1: {self.delta1}")
        print(f"Delta2: {self.delta2}")
        
        if self.logger:
            self.logger.log(f"INIT Execute - Delta1: {self.delta1}, Delta2: {self.delta2}")
    
    def _config_updated(self, new_config):
        """Handle config updates"""
        if 'execution' in new_config:
            execution_config = new_config['execution']
            old_delta1 = self.delta1
            old_delta2 = self.delta2
            
            self.delta1 = execution_config.get('delta1', self.delta1)
            self.delta2 = execution_config.get('delta2', self.delta2)
            self.max_retries = execution_config.get('max_retries', self.max_retries)
            self.retry_delay = execution_config.get('retry_delay', self.retry_delay)
            
            if old_delta1 != self.delta1 or old_delta2 != self.delta2:
                print(f"\nExecute configuration updated:")
                print(f"Delta1: {old_delta1} -> {self.delta1}")
                print(f"Delta2: {old_delta2} -> {self.delta2}")
                if self.logger:
                    self.logger.log(f"Execute config updated - Delta1: {self.delta1}, Delta2: {self.delta2}")
    
    def get_quantity(self, symbol):
        """Get quantity for a symbol from config"""
        quantities = self.execution_config.get('quantities', {})
        return quantities.get(symbol, quantities.get('default', 75))
    
    def round_hundred(self, value):
        """Round the given value to the nearest hundred."""
        return round(value / 100) * 100
    
    def place_order(self, symbol, action, timestamp=''):
        """Wrapper for placing a market order using the Zerodha Kite SDK, with retry logic."""
        quantity = self.get_quantity(symbol)
        self.logger.log(f"Attempting to place order: {symbol} {action} quantity: {quantity}")
        
        for attempt in range(self.max_retries):
            try:
                # Place a market order with the Zerodha Kite SDK
                response = self.client.place_order(
                    variety=self.client.VARIETY_REGULAR,
                    exchange=self.client.EXCHANGE_NFO,  # NSE Futures & Options
                    tradingsymbol=symbol,
                    transaction_type=self.client.TRANSACTION_TYPE_BUY if action == "B" else self.client.TRANSACTION_TYPE_SELL,
                    quantity=quantity,
                    order_type=self.client.ORDER_TYPE_MARKET,
                    product=self.client.PRODUCT_MIS,
                )
                
                self.logger.log(f"Order placed successfully for {symbol} {action} with quantity {quantity}")
                self.excel_logger.log_trade(symbol, action, None, timestamp)
                return True
                
            except Exception as e:
                self.logger.log(f"Error placing order for {symbol}: {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    self.logger.log(f"Retrying... ({attempt + 1}/{self.max_retries})")
        
        self.logger.log(f"Failed to place order for {symbol} after {self.max_retries} attempts.")
        return False
    
    def execute_order(self, symbol, direction, timestamp):
        """Execute an order based on symbol and direction"""
        return self.place_order(symbol, direction, timestamp)
