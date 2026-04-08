"""Upstox WebSocket streamer (async, protobuf)."""
import asyncio
import json
import ssl
import datetime
from typing import List, Dict, Any, Optional

import pytz
import requests
import websockets
from google.protobuf.json_format import MessageToDict

from src.core.event_bus.events import QuoteEvent
from src.system_config_manager import SystemConfigManager
import src.core.streamer.MarketDataFeedV3_pb2 as pb
from .base_streamer import BaseStreamer


class UpstoxStreamer(BaseStreamer):
    """
    Streams real-time data from Upstox via async WebSocket (protobuf feed).

    Requires: upstox-python-sdk, websockets, pytz, protobuf
    access_token must be passed — never hardcoded.
    """

    def __init__(self, symbols: List[str], access_token: str, name_symbol: str = "UPSTOX"):
        super().__init__(symbols, name="UpstoxStreamer")
        if not access_token:
            raise ValueError("access_token is required for UpstoxStreamer")
        self.access_token = access_token
        self.name_symbol = name_symbol
        self._ws_url: Optional[str] = None

    # ------------------------------------------------------------------
    # BaseStreamer interface
    # ------------------------------------------------------------------

    def _setup_connection(self):
        self._ws_url = self._get_ws_url()
        self._logger.info(f"Upstox WS URL obtained")

    def _run_connection(self):
        """Sync entry point — delegates to async loop."""
        asyncio.run(self._run_connection_async())

    async def _run_connection_async(self):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        self._logger.info("Connecting to Upstox WebSocket...")
        async with websockets.connect(self._ws_url, ssl=ssl_ctx) as ws:
            self._logger.info("Upstox WebSocket connected")
            await ws.send(json.dumps({
                "guid": "vwap-streamer",
                "method": "sub",
                "data": {"mode": "full", "instrumentKeys": self.symbols}
            }).encode())
            self._logger.info(f"Subscribed to {len(self.symbols)} instrument(s)")

            while self._is_running and not self._is_market_closed():
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=10)
                    feed = pb.FeedResponse()
                    feed.ParseFromString(message)
                    for instrument_key, tick in MessageToDict(feed).get("feeds", {}).items():
                        event = self._normalize_raw_data(tick, instrument_key)
                        if event:
                            self.publish_quote(event)
                except asyncio.TimeoutError:
                    pass    # heartbeat – keep looping
                except Exception as e:
                    self._logger.error(f"Upstox receive error: {e}")
                    break

        self._logger.info("Upstox WebSocket loop exited")

    def _cleanup_connection(self):
        self._is_running = False    # signals async loop to exit

    def _normalize_raw_data(self, raw_data: Dict[str, Any], symbol: str) -> Optional[QuoteEvent]:
        try:
            ff = (raw_data.get("fullFeed") or {})
            feed = ff.get("marketFF") or ff.get("indexFF") or {}
            ltpc = feed.get("ltpc", {})
            if not ltpc:
                return None
            tz = SystemConfigManager().get("trading_session.timezone", "Asia/Kolkata")
            return QuoteEvent(
                timestamp=datetime.datetime.now(pytz.timezone(tz)),
                source=self.name,
                instrument=symbol,
                name=self.name_symbol,
                ltp=float(ltpc.get("ltp", 0)),
                ltq=float(ltpc.get("ltq", 0) or 0),
            )
        except Exception as e:
            self._logger.error(f"Normalize error for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_ws_url(self) -> str:
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.access_token}"}
        resp = requests.get("https://api.upstox.com/v3/feed/market-data-feed/authorize", headers=headers)
        data = resp.json()
        try:
            return data["data"]["authorized_redirect_uri"]
        except (KeyError, TypeError):
            raise RuntimeError(f"Upstox auth failed: {data}")

    def _is_market_closed(self) -> bool:
        cfg = SystemConfigManager()
        end = cfg.get("trading_session.end_time", "15:30")
        tz  = cfg.get("trading_session.timezone", "Asia/Kolkata")
        h, m = map(int, end.split(":"))
        now = datetime.datetime.now(pytz.timezone(tz))
        return now.hour > h or (now.hour == h and now.minute >= m)
