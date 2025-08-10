"""Upstox streamer implementation using BaseStreamer."""
import json
import websocket
import ssl
from typing import List, Dict, Any

from src.core.streamer import BaseStreamer, QuoteNormalizer
from src.core.streamer.events import QuoteEvent


class UpstoxStreamer(BaseStreamer):
    """Upstox WebSocket streamer implementation."""
    
    def __init__(self, symbols: List[str], access_token: str, name_symbol: str = "UPSTOX"):
        super().__init__(symbols, "UpstoxStreamer")
        self.access_token = access_token
        self.name_symbol = name_symbol
        self._ws = None
        
        # Set up symbol mapping
        for symbol in symbols:
            self.add_symbol_mapping(symbol, name_symbol)

    def _setup_connection(self):
        """Setup Upstox WebSocket connection."""
        url = "wss://ws-api.upstox.com/v3/ws"
        self._ws = websocket.WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
            header=[f"Authorization: Bearer {self.access_token}"]
        )

    def _run_connection(self):
        """Run the WebSocket connection."""
        try:
            self._ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        except Exception as e:
            self._handle_connection_error(e)

    def _cleanup_connection(self):
        """Cleanup WebSocket connection."""
        if self._ws:
            try:
                self._ws.close()
            except Exception as e:
                self._logger.error(f"Error closing WebSocket: {e}")

    def _normalize_raw_data(self, raw_data: Dict[str, Any], symbol: str) -> QuoteEvent:
        """Normalize Upstox tick data to QuoteEvent."""
        return QuoteNormalizer.normalize_upstox_tick(
            raw_data, symbol, self.name
        )

    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            
            if data.get('type') == 'live_feed':
                feeds = data.get('feeds', {})
                for instrument_key, tick_data in feeds.items():
                    if instrument_key in self.symbols:
                        self._process_raw_quote(tick_data, instrument_key)
                        
        except Exception as e:
            self._handle_data_error(e, {'message': message})

    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        self._handle_connection_error(error)

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        self._logger.warning(f"WebSocket closed: {close_status_code} {close_msg}")
        self._is_running = False

    def _on_open(self, ws):
        """Handle WebSocket open and subscribe to symbols."""
        self._logger.info("WebSocket connected to Upstox")
        
        # Subscribe to symbols
        subscribe_message = {
            "guid": "someguid",
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": self.symbols
            }
        }
        ws.send(json.dumps(subscribe_message))
        self._logger.info(f"Subscribed to symbols: {self.symbols}")
