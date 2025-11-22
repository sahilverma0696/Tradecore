"""Upstox streamer implementation using BaseStreamer."""
import json
import ssl
import requests
import websocket
import pytz
import datetime
import asyncio
import websockets
from typing import List, Dict, Any
from google.protobuf.json_format import MessageToDict

from src.core.streamer import BaseStreamer
from src.core.event_bus.events import QuoteEvent
import src.core.streamer.MarketDataFeedV3_pb2 as pb


class UpstoxStreamer(BaseStreamer):
    """Upstox WebSocket streamer implementation."""

    #TODO: full feed event for storage and analysis
    def __init__(self, symbols: List[str], access_token: str, name_symbol: str = "UPSTOX"):
        super().__init__(symbols, name_symbol)
        #TODO: Read access token from config or secure storage
        self.access_token = 'eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiJFUjM5MzkiLCJqdGkiOiI2OTE2YTFkYjNmNWNhODRkMDdjMzk0ZTQiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2MzA5MDkwNywiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzYzMTU3NjAwfQ.mBARe1doZCoF6DpF8lqkCC01PCLvgxaTguZJGWNtzdo' #access_token
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
        try:
            data = api_response.json()
        except Exception as e:
            self._logger.error(f"Failed to parse Upstox API response as JSON: {api_response.text}")
            raise
        if "data" not in data or "authorized_redirect_uri" not in data["data"]:
            self._logger.error(f"Upstox API response missing 'data' or 'authorized_redirect_uri': {data}")
            raise RuntimeError(f"Upstox API response missing 'data' or 'authorized_redirect_uri': {data}")
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

    async def _run_connection_async(self):
        """Async WebSocket connection and message loop using websockets library."""
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        def is_market_closed():
            now = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
            return now.hour > 15 or (now.hour == 15 and now.minute >= 31)

        self._ws_url = self._get_ws_url()
        self._logger.info(f"[ASYNC] Connecting to Upstox WebSocket: {self._ws_url}")
        async with websockets.connect(self._ws_url, ssl=ssl_context) as websocket:
            self._ws_connected = True
            self._logger.info("[ASYNC] WebSocket connection established.")
            await asyncio.sleep(1)
            subscribe_message = {
                "guid": "someguid",
                "method": "sub",
                "data": {
                    "mode": "full",
                    "instrumentKeys": self.symbols
                }
            }
            await websocket.send(json.dumps(subscribe_message).encode('utf-8'))
            self._logger.info(f"[ASYNC] Subscribed to symbols: {self.symbols}")
            while not is_market_closed() and self._is_running:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=10)
                    # self._logger.info(f"[ASYNC] Received message of length {len(message)} bytes")
                    feed_response = pb.FeedResponse()
                    feed_response.ParseFromString(message)
                    feed_dict = MessageToDict(feed_response)
                    feeds = feed_dict.get("feeds", {})
                    if not feeds:
                        self._logger.warning(f"[ASYNC] No feeds in message: {feed_dict}")
                    for instrument_key, tick_data in feeds.items():
                        # self._logger.info(f"[ASYNC] Feed for {instrument_key}: {tick_data}")
                        event = self._normalize_raw_data(tick_data, instrument_key)
                        if event:
                            self.publish_quote(event)
                except asyncio.TimeoutError:
                    self._logger.info("[ASYNC] No data received in 10 seconds. Still listening...")
                except Exception as e:
                    self._logger.error(f"[ASYNC] Error receiving/parsing data: {e}")
            self._logger.info("[ASYNC] Market closed or stopped. Exiting WebSocket loop.")
            self._ws_connected = False

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
            self._logger.info(f"Received message of length {len(message)} bytes")
            # Upstox sends protobuf binary, not JSON
            feed_response = pb.FeedResponse()
            feed_response.ParseFromString(message)
            feed_dict = MessageToDict(feed_response)
            feeds = feed_dict.get("feeds", {})
            if not feeds:
                self._logger.warning(f"No feeds in message: {feed_dict}")
            for instrument_key, tick_data in feeds.items():
                self._logger.info(f"Feed for {instrument_key}: {tick_data}")
                event = self._normalize_raw_data(tick_data, instrument_key)
                if event:
                    self.publish_quote(event)
        except Exception as e:
            self._logger.error(f"Error parsing Upstox message: {e} (raw: {message})")

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
            self._logger.info(f"[NORMALIZE] Raw data for {symbol}: {raw_data}")
            full_feed = raw_data.get("fullFeed", {})
            # Try both marketFF (for stocks/futures) and indexFF (for indices)
            ff = full_feed.get("marketFF") or full_feed.get("indexFF") or {}
            ltpc_data = ff.get("ltpc", {})
            if not ltpc_data:
                self._logger.warning(f"[NORMALIZE] No ltpc_data for {symbol}: {ff}")
                return None
            ltp = float(ltpc_data.get("ltp", 0))
            # Some feeds may not have ltq (quantity), default to 0
            ltq = int(ltpc_data.get("ltq", "0")) if "ltq" in ltpc_data else 0
            ts = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
            event = QuoteEvent(
                timestamp=ts,
                instrument=symbol,
                name=self.name_symbol,
                ltp=ltp,
                ltq=ltq,
                source=self.name
            )
            self._logger.info(f"[NORMALIZE] Created QuoteEvent: {event}")
            return event
        except Exception as e:
            self._logger.error(f"Error normalizing Upstox data: {e}")
            return None

    def publish_quote(self, event):
        # self._logger.info(f"[PUBLISH] Publishing event: {event}")
        super().publish_quote(event)
