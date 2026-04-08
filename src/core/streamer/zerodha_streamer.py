"""Zerodha KiteTicker streamer."""
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.core.event_bus.events import QuoteEvent
from .base_streamer import BaseStreamer


class ZerodhaStreamer(BaseStreamer):
    """
    Streams real-time ticks via Zerodha KiteTicker.

    Requires kiteconnect: pip install kiteconnect
    Call init_kite(access_token) before start().
    """

    def __init__(
        self,
        symbols: List[int],
        *,
        api_key: str,
        access_token: str = None,
        name_symbol: str = "ZERODHA",
    ):
        # BaseStreamer stores symbols as strings internally
        super().__init__([str(s) for s in symbols], name="ZerodhaStreamer")
        self._int_symbols = list(symbols)   # Kite needs ints
        self.api_key = api_key
        self.access_token = access_token
        self.name_symbol = name_symbol
        self._kite = None
        self._ticker = None

    # ------------------------------------------------------------------
    # Kite initialisation (call before start)
    # ------------------------------------------------------------------

    def init_kite(self, access_token: str = None):
        """Connect to Kite API. Raises if kiteconnect is not installed."""
        try:
            from kiteconnect import KiteConnect, KiteTicker
        except ImportError:
            raise RuntimeError("kiteconnect not installed – pip install kiteconnect")

        token = access_token or self.access_token
        if not token:
            raise RuntimeError("access_token required for ZerodhaStreamer")

        self._kite = KiteConnect(api_key=self.api_key)
        self._kite.set_access_token(token)
        self.access_token = token
        self._logger.info("Kite client initialised")

    # ------------------------------------------------------------------
    # BaseStreamer interface
    # ------------------------------------------------------------------

    def _setup_connection(self):
        if not self._kite:
            raise RuntimeError("Call init_kite() before starting ZerodhaStreamer")
        try:
            from kiteconnect import KiteTicker
        except ImportError:
            raise RuntimeError("kiteconnect not installed")

        self._ticker = KiteTicker(self.api_key, self.access_token)
        self._ticker.on_ticks   = self._on_ticks
        self._ticker.on_connect = self._on_connect
        self._ticker.on_close   = self._on_close
        self._ticker.on_error   = self._on_error

    def _run_connection(self):
        self._ticker.connect(threaded=False)

    def _cleanup_connection(self):
        if self._ticker:
            try:
                self._ticker.close()
            except Exception as e:
                self._logger.error(f"Ticker close error: {e}")
            self._ticker = None

    def _normalize_raw_data(self, raw_data: Dict[str, Any], symbol: str) -> Optional[QuoteEvent]:
        try:
            ltp = float(raw_data.get('last_price', 0))
            ltq = float(raw_data.get('last_traded_quantity', 0))
            ts  = raw_data.get('timestamp') or datetime.now()
            return QuoteEvent(
                timestamp=ts,
                source=self.name,
                instrument=symbol,
                name=self.name_symbol,
                ltp=ltp,
                ltq=ltq,
            )
        except Exception as e:
            self._logger.error(f"Normalize error for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------
    # KiteTicker callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, ws, response):
        self._logger.info("KiteTicker connected – subscribing")
        ws.subscribe(self._int_symbols)
        ws.set_mode(ws.MODE_FULL, self._int_symbols)

    def _on_ticks(self, ws, ticks):
        for tick in ticks:
            tok = tick.get('instrument_token')
            if tok not in self._int_symbols:
                continue
            event = self._normalize_raw_data(tick, str(tok))
            if event:
                self.publish_quote(event)

    def _on_close(self, ws, code, reason):
        self._logger.warning(f"KiteTicker closed: {code} {reason}")
        self._is_running = False

    def _on_error(self, ws, code, reason):
        self._logger.error(f"KiteTicker error: {code} {reason}")
