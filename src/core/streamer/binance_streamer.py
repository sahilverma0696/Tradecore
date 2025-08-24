"""Live Binance trade streamer for real-time market data."""
import time
import json
import websocket
import ssl
from datetime import datetime
from typing import List, Dict, Any

from .base_streamer import BaseStreamer
from src.core.thread_manager import ThreadManager, ThreadPoolType
from src.core.event_bus.events import QuoteEvent

class BinanceStreamer(BaseStreamer):
    """Binance WebSocket streamer for trade data from futures."""

    def __init__(self, symbols: List[str], name_symbol: str, **kwargs):
        # Initialize BaseStreamer which includes Publisher mixin
        super().__init__(symbols, name_symbol)
        self.name_symbol = name_symbol
        self._ws = None
        
        # Handle additional configuration from kwargs
        self.reconnect_attempts = kwargs.get('reconnect_attempts', 3)
        self.reconnect_delay = kwargs.get('reconnect_delay', 5.0)
        self.testnet = kwargs.get('testnet', False)
        
        self._logger.info(f"BinanceStreamer initialized for trade streaming: {symbols}")

    def _setup_connection(self):
        """Setup Binance WebSocket connection."""
        if not self.symbols:
            raise ValueError("No symbols provided for Binance WebSocket.")

        # Create direct trade stream URL like sample_binance.py
        ws_url = "wss://stream.binance.com:9443/ws/" + "/".join([f"{symbol.lower()}@trade" for symbol in self.symbols])
            
        self._logger.info(f"Setting up Binance WebSocket: {ws_url}")
        
        # Create WebSocket application exactly like sample_binance.py
        self._ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )

    def _run_connection(self):
        """Run the WebSocket connection."""
        def _run_websocket():
            """Internal function to run WebSocket in thread pool."""
            try:
                self._logger.info("Starting Binance WebSocket connection...")
                self._ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
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
            event = self._normalize_raw_data(data, self.name_symbol)
            if event:
                self.publish_quote(event)
                    
        except Exception as e:
            self._logger.error(f"Error parsing Binance message: {e}")

    def _normalize_raw_data(self, raw_data, symbol):
        """Normalize raw Binance trade data to QuoteEvent."""
        try:
            # Extract trade data (like sample_binance.py)
            price = float(raw_data.get('p', 0))     # Trade price
            quantity = float(raw_data.get('q', 0))  # Trade quantity
            trade_symbol = raw_data.get('s', '').upper()  # Symbol
            trade_time = raw_data.get('T', 0)       # Trade time
            
            return QuoteEvent(
                timestamp=trade_time,
                instrument=trade_symbol,
                name=symbol,
                ltp=price,
                ltq=quantity,
                source=self.name
            )
        except Exception as e:
            self._logger.error(f"Error normalizing Binance data: {e}")
            return None

    def _on_open(self, ws):
        """Handle WebSocket connection open."""
        self._logger.info("Binance WebSocket connection opened")


    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        self._logger.error(f"Binance WebSocket error: {error}")

    def get_client(self):
        """Get the Binance client instance (if available)."""
        return getattr(self, '_client', None)
    

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection close."""
        self._logger.warning(f"Binance WebSocket closed: {close_status_code} - {close_msg}")
        self._is_subscribed = False

    
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


        