"""Upstox streamer implementation using BaseStreamer."""
import json
import ssl
import requests
import websocket
import pytz
import datetime
from typing import List, Dict, Any
from google.protobuf.json_format import MessageToDict

from src.core.streamer import BaseStreamer
from src.core.event_bus.events import QuoteEvent
import src.core.streamer.MarketDataFeedV3_pb2 as pb


class UpstoxStreamer(BaseStreamer):
    """Upstox WebSocket streamer implementation."""

    def __init__(self, symbols: List[str], access_token: str, name_symbol: str = "UPSTOX"):
        super().__init__(symbols, name_symbol)
        self.access_token = access_token
        self.name_symbol = name_symbol
        self._ws = None
        self._ws_url = None
        self._ws_connected = False
        self._logger.info(f"UpstoxStreamer initialized for: {symbols}")

    def _get_ws_url(self):
        """Authorize and get the Upstox WebSocket URL."""
        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }
        url = 'https://api.upstox.com/v3/feed/market-data-feed/authorize'
        api_response = requests.get(url=url, headers=headers)
        data = api_response.json()
        ws_url = data["data"]["authorized_redirect_uri"]
        return ws_url

    def _setup_connection(self):
        """Setup Upstox WebSocket connection."""
        self._ws_url = self._get_ws_url()
        self._logger.info(f"Setting up Upstox WebSocket: {self._ws_url}")
        self._ws = websocket.WebSocketApp(
            self._ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )

    def _run_connection(self):
        """Run the WebSocket connection."""
        try:
            if self._ws and not self._ws_connected:
                self._logger.info("Starting Upstox WebSocket connection...")
                self._ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
            else:
                self._logger.warning("WebSocket already connected or not initialized")
        except Exception as e:
            self._logger.error(f"WebSocket run_forever error: {e}")
            self._ws_connected = False
            raise

    def _cleanup_connection(self):
        """Cleanup WebSocket connection."""
        if self._ws and self._ws_connected:
            try:
                self._ws.close()
                self._logger.info("Upstox WebSocket connection closed")
            except Exception as e:
                self._logger.error(f"Error closing WebSocket: {e}")
            finally:
                self._ws_connected = False
                self._ws = None

    def _on_open(self, ws):
        """Handle WebSocket open and subscribe to symbols."""
        self._ws_connected = True
        self._logger.info("WebSocket connected to Upstox")
        subscribe_message = {
            "guid": "someguid",
            "method": "sub",
            "data": {
                "mode": "full",
                "instrumentKeys": self.symbols
            }
        }
        ws.send(json.dumps(subscribe_message).encode('utf-8'))
        self._logger.info(f"Subscribed to symbols: {self.symbols}")

    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages (protobuf)."""
        try:
            # Upstox sends protobuf binary, not JSON
            feed_response = pb.FeedResponse()
            feed_response.ParseFromString(message)
            feed_dict = MessageToDict(feed_response)
            feeds = feed_dict.get("feeds", {})
            for instrument_key, tick_data in feeds.items():
                event = self._normalize_raw_data(tick_data, instrument_key)
                if event:
                    self.publish_quote(event)
        except Exception as e:
            self._logger.error(f"Error parsing Upstox message: {e}")

    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        self._logger.error(f"Upstox WebSocket error: {error}")
        self._ws_connected = False

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close."""
        self._logger.warning(f"WebSocket closed: {close_status_code} {close_msg}")
        self._ws_connected = False
        self._is_running = False

    def _normalize_raw_data(self, raw_data: Dict[str, Any], symbol: str) -> QuoteEvent:
        """Normalize Upstox tick data to QuoteEvent."""
        try:
            # Extract fullFeed/marketFF/ltpc fields
            market_ff = raw_data.get("fullFeed", {}).get("marketFF", {})
            ltpc_data = market_ff.get("ltpc", {})
            if not ltpc_data:
                return None
            ltp = float(ltpc_data.get("ltp", 0))
            ltq = int(ltpc_data.get("ltq", "0"))
            cp = float(ltpc_data.get("cp", 0))
            ts = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
            return QuoteEvent(
                timestamp=ts,
                instrument=symbol,
                name=self.name_symbol,
                ltp=ltp,
                ltq=ltq,
                source=self.name,
                cp=cp
            )
        except Exception as e:
            self._logger.error(f"Error normalizing Upstox data: {e}")
            return None
