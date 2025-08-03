"""Live Binance ticker to quote handler pipeline."""
import threading
import time
from typing import Callable, List
import json
import websocket
import ssl
import traceback

from src.logger_factory import get_logger

class BinanceStreamer:
    def __init__(self, symbols: List[str], name_symbol: str):
        self.symbols = symbols  # Binance symbols, e.g., ['btcusdt', 'ethusdt']
        self.name_symbol = name_symbol
        self._logger = get_logger("BinanceStreamer")
        self._handlers: List[Callable[[dict], None]] = []
        self._ws = None
        self._thread = None

    def register_handler(self, cb):
        if callable(cb):
            self._logger.debug(f"Registering handler {cb.__name__}")
            self._handlers.append(cb)

    def _on_message(self, ws, message):
        # self._logger.debug(f"Received message: {message}")  # <-- Add logging
        try:
            data = json.loads(message)
            # Binance multiplexed streams wrap data in 'stream' and 'data'
            if 'stream' in data and 'data' in data:
                data = data['data']
            # For ticker, use 'data' or direct fields
            if 'e' in data and data['e'] == '24hrTicker':
                compat_quote = {
                    'ts': data.get('E'),
                    'inst': data.get('s'),
                    'name': self.name_symbol,
                    'ltp': float(data.get('c', 0)),
                    'volume': float(data.get('v', 0)),
                    'change': float(data.get('P', 0))
                }
                # self._logger.debug(f"Compat quote: {compat_quote}")  # <-- Add logging
                for cb in self._handlers:
                    try:
                        cb(compat_quote)
                    except Exception as e:
                        self._logger.error(f"handler error: {e}\n{traceback.format_exc()}")
        except Exception as e:
            self._logger.error(f"Error parsing message: {e}\n{traceback.format_exc()}")

    def _on_error(self, ws, error):
        self._logger.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        self._logger.warning(f"WebSocket closed: {close_status_code} {close_msg}")

    def _on_open(self, ws):
        self._logger.info("WebSocket connected.")
        # No need to send subscribe message for multiplexed streams

    def _run_ws(self):
        # Helper to run websocket with SSL options
        self._logger.info("Starting WebSocket thread... _run_ws")
        self._ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    def start(self):
        # Binance allows multiplexing streams with a single connection
        self._logger.info("Starting Binance WebSocket connection...")
        self._logger.debug(f"Symbols: {self.symbols}")  # <-- Add logging
        if not self.symbols:
            self._logger.error("No symbols provided for Binance WebSocket.")
            return
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
        self._thread = threading.Thread(target=self._run_ws, daemon=True)
        self._thread.start()
        self._logger.info("WebSocket thread started.")

    def get_client(self):
        # Return the Binance client instance (assume it's set up elsewhere)
        return self._client if hasattr(self, '_client') else None
