from datetime import datetime
import time
import json
import traceback
from src.logger_factory import get_logger
from src.config_manager import ConfigManager

class ZerodhaExecute:
    def __init__(self, excel_logger, expiry, client):
        self.config_manager = ConfigManager()
        self.config_manager.register_watcher(self._config_updated)
        
        # Load trading configuration
        with open('trading_config.json', 'r') as f:
            self.config = json.load(f)
        
        # Get execution config
        self.execution_config = self.config['execution']
        self.delta_sell = self.execution_config.get('delta_sell')
        self.delta_buy = self.execution_config.get('delta_buy', 0)
        self.max_retries = self.execution_config.get('max_retries', 2)
        self.retry_delay = self.execution_config.get('retry_delay', 1)
        
        self.logger = get_logger("ZerodhaExecute")  # An instance of Logger to log messages
        self.excel_logger = excel_logger  # An instance of ExcelTradeLogger for logging trades
        self.expiry = expiry  # Expiry date for options
        self.state = None  # Track current trade direction ('long' or 'short')
        self.open_trades = {}  # Dictionary to store open trades with entry prices and timestamps
        self.closed_trades = []  # List to store last closed positions
        self.client = client

        print(f"\nInitializing ZerodhaExecute with configuration:")
        print(f"Delta SELL: {self.delta_sell}")
        print(f"Delta BUY: {self.delta_buy}")
        
        if self.logger:
            self.logger.debug(f"INIT ZerodhaExecute - Delta SELL: {self.delta_sell}, Delta BUY: {self.delta_buy}, Max Retries: {self.max_retries}, Retry Delay: {self.retry_delay}")
    
    def _config_updated(self, new_config):
        """Handle config updates"""
        if 'execution' in new_config:
            execution_config = new_config['execution']
            old_delta_sell = self.delta_sell
            old_delta_buy = self.delta_buy
            
            self.delta_sell = execution_config.get('delta_sell', self.delta_sell)
            self.delta_buy = execution_config.get('delta_buy', self.delta_buy)
            self.max_retries = execution_config.get('max_retries', self.max_retries)
            self.retry_delay = execution_config.get('retry_delay', self.retry_delay)
            
            if old_delta_sell != self.delta_sell or old_delta_buy != self.delta_buy:
                print(f"\nZerodhaExecute configuration updated:")
                print(f"delta_sell: {old_delta_sell} -> {self.delta_sell}")
                print(f"delta_buy: {old_delta_buy} -> {self.delta_buy}")
                if self.logger:
                    self.logger.debug(f"ZerodhaExecute config updated - delta_sell: {self.delta_sell}, delta_buy: {self.delta_buy}")
    
    def get_quantity(self, symbol):
        """Get quantity for a symbol from config"""
        ## Get quantities from execution config based on symbol and buy or sell action
        quantities = self.execution_config.get('quantities', {})
        return quantities.get(symbol, quantities.get('default', 75))
    
    def round_hundred(self, value):
        """Round the given value to the nearest hundred."""
        return round(value / 100) * 100
    
    def place_order(self, symbol, action, timestamp=''):
        """Wrapper for placing a market order using the Zerodha Kite SDK, with retry logic.
        Args:
            symbol (str): The trading symbol for the order.
            action (str): 'B' for buy, 'S' for sell.
            timestamp (str): Optional timestamp for the order, defaults to current time if not provided.
        Returns:
            bool: True if order was placed successfully, False otherwise.
        """
        quantity = self.get_quantity(symbol)
        self.logger.debug(f"Attempting to place order: {symbol} {action} quantity: {quantity}")
        
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
                
                self.logger.debug(f"Order placed successfully for {symbol} {action} with quantity {quantity}")
                self.excel_logger.log_trade(symbol, action, None, timestamp)
                return True
                
            except Exception as e:
                self.logger.debug(f"Error placing order for {symbol}: {str(e)}\n{traceback.format_exc()}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    self.logger.debug(f"Retrying... ({attempt + 1}/{self.max_retries})")
        
        self.logger.debug(f"Failed to place order for {symbol} after {self.max_retries} attempts.")
        return False
    
    def execute_order(self, symbol, direction, timestamp):
        """ZerodhaExecute an order based on symbol and direction"""
        return self.place_order(symbol, direction, timestamp)
