from datetime import datetime
import time
import json
import traceback
from src.logger_factory import get_logger
from src.config_manager import ConfigManager

class BinanceExecute:
    def __init__(self, excel_logger, client):
        self.config_manager = ConfigManager()
        self.config_manager.register_watcher(self._config_updated)

        # Load trading configuration
        with open('trading_config.json', 'r') as f:
            self.config = json.load(f)

        # Get execution config
        self.execution_config = self.config.get('execution', {})
        self.delta_sell = self.execution_config.get('delta_sell')
        self.delta_buy = self.execution_config.get('delta_buy', 0)
        self.max_retries = self.execution_config.get('max_retries', 2)
        self.retry_delay = self.execution_config.get('retry_delay', 1)

        self.logger = get_logger("BinanceExecute")
        self.excel_logger = excel_logger
        self.state = None
        self.open_trades = {}
        self.closed_trades = []
        self.client = client

        print(f"\nInitializing BinanceExecute with configuration:")
        print(f"Delta SELL: {self.delta_sell}")
        print(f"Delta BUY: {self.delta_buy}")

        if self.logger:
            self.logger.debug(f"INIT BinanceExecute - Delta SELL: {self.delta_sell}, Delta BUY: {self.delta_buy}, Max Retries: {self.max_retries}, Retry Delay: {self.retry_delay}")

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
                print(f"\nBinanceExecute configuration updated:")
                print(f"delta_sell: {old_delta_sell} -> {self.delta_sell}")
                print(f"delta_buy: {old_delta_buy} -> {self.delta_buy}")
                if self.logger:
                    self.logger.debug(f"BinanceExecute config updated - delta_sell: {self.delta_sell}, delta_buy: {self.delta_buy}")

    def get_quantity(self, symbol):
        """Get quantity for a symbol from config"""
        quantities = self.execution_config.get('quantities', {})
        return quantities.get(symbol, quantities.get('default', 0.01))  # Default for Binance spot/futures

    def place_order(self, symbol, action, timestamp=''):
        """Place a market order using Binance client, with retry logic.
        Args:
            symbol (str): Binance symbol, e.g., 'BTCUSDT'
            action (str): 'B' for buy, 'S' for sell
            timestamp (str): Optional timestamp
        Returns:
            bool: True if order placed, False otherwise
        """
        quantity = self.get_quantity(symbol)
        self.logger.debug(f"Attempting to place Binance order: {symbol} {action} quantity: {quantity}")

        for attempt in range(self.max_retries):
            try:
                # Place a market order using Binance client
                side = 'BUY' if action == 'B' else 'SELL'
                response = self.client.create_order(
                    symbol=symbol,
                    side=side,
                    type='MARKET',
                    quantity=quantity
                )
                self.logger.debug(f"Binance order placed successfully for {symbol} {action} with quantity {quantity}")
                self.excel_logger.log_trade(symbol, action, None, timestamp)
                return True

            except Exception as e:
                self.logger.debug(f"Error placing Binance order for {symbol}: {str(e)}\n{traceback.format_exc()}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    self.logger.debug(f"Retrying... ({attempt + 1}/{self.max_retries})")

        self.logger.debug(f"Failed to place Binance order for {symbol} after {self.max_retries} attempts.")
        return False

    def execute_order(self, symbol, direction, timestamp):
        """ZerodhaExecute an order based on symbol and direction"""
        return self.place_order(symbol, direction, timestamp)
