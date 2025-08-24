"""Live Binance mark price streamer for futures market data."""
import time
import json
import websocket
import ssl
import threading
from datetime import datetime
from typing import List, Dict, Any

from .base_streamer import BaseStreamer
from src.core.thread_manager import ThreadManager, ThreadPoolType

class BinanceStreamer(BaseStreamer):
    """Binance WebSocket streamer for mark price data from futures."""
    
    def __init__(self, symbols: List[str], name_symbol: str = "CRYPTO", **kwargs):
        # Initialize BaseStreamer which includes Publisher mixin
        super().__init__(symbols, name_symbol)
        self.name_symbol = name_symbol
        self._ws = None
        self._ws_thread = None
        
        # Handle additional configuration from kwargs
        self.reconnect_attempts = kwargs.get('reconnect_attempts', 3)
        self.reconnect_delay = kwargs.get('reconnect_delay', 5.0)
        self.stream_timeout = kwargs.get('stream_timeout', 60)
        self.ping_interval = kwargs.get('ping_interval', 180)
        self.testnet = kwargs.get('testnet', False)
        
        # Only support mark price streams
        self.stream_type = 'markPrice'
        
        # WebSocket management
        self._subscription_id = 1
        self._is_subscribed = False
        
        self._logger.info(f"BinanceStreamer initialized for mark price streaming: {symbols}")

    def _setup_connection(self):
        """Setup Binance WebSocket connection."""
        if not self.symbols:
            raise ValueError("No symbols provided for Binance WebSocket.")


        ws_url = "wss://stream.binance.com:9443/ws/"+"/".join([f"{symbol.lower()}@trade" for symbol in self.symbols])
            
        self._logger.info(f"Setting up Binance WebSocket: {ws_url}")
        
        # Create WebSocket application
        self._ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )

    def _run_connection(self):
        """Run the WebSocket connection with subscription management."""
        def _run_websocket():
            """Internal function to run WebSocket in thread pool."""
            try:
                self._logger.info("Starting Binance WebSocket connection...")
                self._ws.run_forever(
                    sslopt={"cert_reqs": ssl.CERT_NONE}
                    )
            except Exception as e:
                self._logger.error(f"WebSocket run_forever error: {e}")
                raise

        # Submit WebSocket connection to thread pool
        thread_manager = ThreadManager()
        self._ws_future = thread_manager.submit_task(
            ThreadPoolType.STREAMER,
            _run_websocket
        )
        
        self._logger.info("WebSocket connection task submitted to thread pool")

    def _cleanup_connection(self):
        """Cleanup WebSocket connection."""
        if self._is_subscribed:
            self._unsubscribe_from_symbols()
        
        if self._ws:
            try:
                self._ws.close()
                self._logger.info("Binance WebSocket connection closed")
            except Exception as e:
                self._logger.error(f"Error closing WebSocket: {e}")

    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            
            # Handle subscription confirmations
            if 'result' in data and data.get('id') == self._subscription_id:
                if data['result'] is None:
                    self._logger.info("Successfully subscribed to Binance mark price streams")
                    self._is_subscribed = True
                else:
                    self._logger.error(f"Subscription failed: {data}")
                return
            
            # Handle mark price updates only
            if 'e' in data and data['e'] == 'markPriceUpdate':
                self._process_mark_price_data(data)
                    
        except Exception as e:
            self._logger.error(f"Error parsing Binance message: {e}")

    def _process_mark_price_data(self, mark_price_data):
        """Process Mark Price Stream data from Binance futures and publish to EventBus."""
        try:
            # Extract data from mark price update
            symbol = mark_price_data.get('s', '').upper()
            if not symbol:
                return
            
            # Convert Binance timestamp (milliseconds) to datetime
            timestamp_ms = mark_price_data.get('E')
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000) if timestamp_ms else datetime.now()
            
            # Extract mark price data
            mark_price = float(mark_price_data.get('p', 0))      # Mark price
            index_price = float(mark_price_data.get('i', 0))     # Index price
            funding_rate = float(mark_price_data.get('r', 0))    # Funding rate
            next_funding_time = mark_price_data.get('T', 0)      # Next funding time
            
            # Use mark price as LTP for trading decisions
            ltp = mark_price
            volume = 0  # Mark price stream doesn't include volume
            
            # Use BaseStreamer's publish_quote method which publishes to EventBus
            self.publish_quote(
                symbol=symbol,
                ltp=ltp,
                volume=volume,
                bid=0,  # Not available in mark price stream
                ask=0,  # Not available in mark price stream
                raw_data={
                    **mark_price_data,
                    'mark_price': mark_price,
                    'index_price': index_price,
                    'funding_rate': funding_rate,
                    'next_funding_time': next_funding_time,
                    'stream_type': 'markPrice'
                }
            )
            
            self._logger.info(f"📊 {symbol} Mark Price: ${mark_price:.2f} | Index: ${index_price:.2f} | Funding: {funding_rate:.6f}")
            
        except Exception as e:
            self._logger.error(f"Error processing Binance mark price data: {e}")

    def _on_open(self, ws):
        """Handle WebSocket connection open."""
        self._logger.info("Binance WebSocket connection opened")

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close."""
        self._logger.warning(f"Binance WebSocket closed: {close_status_code} - {close_msg}")
        self._is_subscribed = False

    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        self._logger.error(f"Binance WebSocket error: {error}")

    
    def _unsubscribe_from_symbols(self):
        """Unsubscribe from mark price WebSocket streams."""
        try:
            if not self._is_subscribed:
                return
                
            # Create mark price stream parameters for unsubscription
            params = [f"{symbol.lower()}@markPrice@1s" for symbol in self.symbols]
            
            unsubscription_message = {
                "method": "UNSUBSCRIBE", 
                "params": params,
                "id": self._subscription_id + 1
            }
            
            self._logger.info(f"Unsubscribing from Binance mark price streams: {params}")
            self._ws.send(json.dumps(unsubscription_message))
            self._is_subscribed = False
            
        except Exception as e:
            self._logger.error(f"Error unsubscribing from symbols: {e}")

    def get_client(self):
        """Get the Binance client instance (if available)."""
        return getattr(self, '_client', None)
        