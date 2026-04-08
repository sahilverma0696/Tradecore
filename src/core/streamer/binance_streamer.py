"""Binance WebSocket trade streamer."""
import json
import ssl
import time
try:
    import certifi
    _SSL_OPT = {"ca_certs": certifi.where()}
except ImportError:
    _SSL_OPT = {"cert_reqs": ssl.CERT_NONE}
from datetime import datetime
from typing import List, Dict, Any, Optional

import websocket

from src.core.event_bus.events import QuoteEvent
from .base_streamer import BaseStreamer


class BinanceStreamer(BaseStreamer):
    """Streams real-time trade data from Binance via WebSocket."""

    def __init__(
        self,
        symbols: List[str],
        reconnect_attempts: int = 5,
        reconnect_delay: float = 2.0,
        stream_timeout: int = 60,
        testnet: bool = False,
        **kwargs,
    ):
        super().__init__(symbols, name="BinanceStreamer")
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.stream_timeout = stream_timeout
        self.testnet = testnet
        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_connected = False
        self._attempt = 0

    # ------------------------------------------------------------------
    # BaseStreamer interface
    # ------------------------------------------------------------------

    def _setup_connection(self):
        if not self.symbols:
            raise ValueError("No symbols provided")
        streams = "/".join(f"{s.lower()}@trade" for s in self.symbols)
        base = "wss://testnet.binance.vision/ws" if self.testnet else "wss://stream.binance.com:9443/ws"
        ws_url = f"{base}/{streams}"
        self._logger.info(f"Connecting to {ws_url}")
        self._ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open,
        )

    def _run_connection(self):
        """Run WebSocket with reconnect loop."""
        for attempt in range(self.reconnect_attempts):
            if not self._is_running:
                break
            try:
                self._logger.info(f"WebSocket connect attempt {attempt + 1}/{self.reconnect_attempts}")
                self._ws.run_forever(sslopt=_SSL_OPT)
                if not self._is_running:
                    break           # clean stop requested
            except Exception as e:
                self._logger.error(f"WebSocket error on attempt {attempt + 1}: {e}")

            if attempt < self.reconnect_attempts - 1 and self._is_running:
                self._logger.info(f"Reconnecting in {self.reconnect_delay}s...")
                time.sleep(self.reconnect_delay)
                self._setup_connection()    # fresh ws object

        if self._is_running:
            self._logger.error("All reconnect attempts exhausted – streamer stopping")
            self._is_running = False

    def _cleanup_connection(self):
        if self._ws and self._ws_connected:
            try:
                self._ws.close()
            except Exception as e:
                self._logger.error(f"WebSocket close error: {e}")
            finally:
                self._ws_connected = False
                self._ws = None

    def _normalize_raw_data(self, raw_data: Dict[str, Any], symbol: str) -> Optional[QuoteEvent]:
        try:
            price = float(raw_data.get('p', 0))
            qty = float(raw_data.get('q', 0))
            trade_symbol = raw_data.get('s', symbol).upper()
            ts_ms = raw_data.get('T', 0)
            ts = datetime.fromtimestamp(ts_ms / 1000) if ts_ms else datetime.now()
            return QuoteEvent(
                timestamp=ts,
                source=self.name,
                instrument=trade_symbol,
                name=trade_symbol,
                ltp=price,
                ltq=qty,
            )
        except Exception as e:
            self._logger.error(f"Normalize error: {e}")
            return None

    # ------------------------------------------------------------------
    # WebSocket callbacks
    # ------------------------------------------------------------------

    def _on_open(self, ws):
        self._ws_connected = True
        self._logger.info("Binance WebSocket opened")

    def _on_close(self, ws, code, msg):
        self._ws_connected = False
        self._logger.warning(f"Binance WebSocket closed: {code} {msg}")

    def _on_error(self, ws, error):
        self._logger.error(f"Binance WebSocket error: {error}")
        self._ws_connected = False

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            event = self._normalize_raw_data(data, self.symbols[0] if self.symbols else "")
            if event:
                self.publish_quote(event)
        except Exception as e:
            self._logger.error(f"Message parse error: {e}")
