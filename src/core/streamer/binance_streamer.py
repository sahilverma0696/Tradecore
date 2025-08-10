"""Live Binance ticker to quote handler pipeline."""
import threading
import time
from typing import List, Dict, Any
import json
import websocket
import ssl
import traceback
from datetime import datetime

from src.logger_factory import get_logger
from src.core.event_bus import Publisher, QuoteEvent, FullQuoteEvent

class BinanceStreamer(Publisher):
    def __init__(self, symbols: List[str], name_symbol: str):
        super().__init__()
        self.symbols = symbols  # Binance symbols, e.g., ['btcusdt', 'ethusdt']
        self.name_symbol = name_symbol
        self._logger = get_logger("BinanceStreamer")
        self._ws = None
        self._thread = None

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            # Binance multiplexed streams wrap data in 'stream' and 'data'
            if 'stream' in data and 'data' in data:
                data = data['data']
            # For ticker, use 'data' or direct fields
            if 'e' in data and data['e'] == '24hrTicker':
                # Convert Binance timestamp (milliseconds) to datetime
                timestamp_ms = data.get('E')
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000) if timestamp_ms else datetime.now()
                symbol = data.get('s')
                
                if symbol:
                    # Publish simplified QuoteEvent
                    quote_event = QuoteEvent(
                        timestamp=timestamp,
                        source=self.__class__.__name__,
                        instrument=symbol,
                        name=self.name_symbol,
                        ltp=float(data.get('c', 0)),
                        ltq=0  # Not available in ticker stream
                    )
                    self.publish_event(quote_event)
                    
                    # Publish FullQuoteEvent for database storage
                    full_quote_event = FullQuoteEvent(
                        timestamp=timestamp,
                        source=self.__class__.__name__,
                        instrument=symbol,
                        name=self.name_symbol,
                        raw_data=data  # Complete raw ticker data
                    )
                    self.publish_event(full_quote_event)
                    
        except Exception as e:
            self._logger.error(f"Error parsing message: {e}\n{traceback.format_exc()}")

    # BaseStreamer abstract methods implementation
    def _setup_connection(self):
        """Setup Binance WebSocket connection."""
        if not self.symbols:
            raise ValueError("No symbols provided for Binance WebSocket.")
        
        streams = '/'.join([f"{symbol.lower()}@ticker" for symbol in self.symbols])
        url = f"wss://stream.binance.com:9443/stream?streams={streams}"
        self._logger.info(f"Connecting to Binance WebSocket: {url}")
        
        self._ws = websocket.WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
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

    def get_client(self):
        # Return the Binance client instance (assume it's set up elsewhere)
        return getattr(self, '_client', None)
        """Get the Binance client instance."""
        return getattr(self, '_client', None)
