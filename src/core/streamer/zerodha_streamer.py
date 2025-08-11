"""Live Zerodha ticker to quote handler pipeline."""
from datetime import datetime
import threading
import time
from typing import List, Dict, Any

from kiteconnect import KiteConnect, KiteTicker

from src.logger_factory import get_logger
from src.core.executioner import Execute
from src.core.event_bus import Publisher, QuoteEvent, FullQuoteEvent
from .base_streamer import BaseStreamer
from .quote_normalizer import QuoteNormalizer
from .events import QuoteEvent


class ZerodhaStreamer(BaseStreamer):
    """Zerodha KiteTicker streamer implementation."""
    
    def __init__(
        self,
        symbols: List[int],
        *,
        api_key: str,
        api_secret: str,
        name_symbol: str,
        paper_trade: bool = True,
    ):
        # Convert int symbols to strings for BaseStreamer
        symbol_strings = [str(s) for s in symbols]
        super().__init__(symbol_strings, name="ZerodhaStreamer")
        
        self.symbols = symbols  # Keep original int symbols for Kite
        self.api_key = api_key
        self.api_secret = api_secret
        self.name_symbol = name_symbol
        self._kite: KiteConnect | None = None
        self._ticker: KiteTicker | None = None
        self._paper = paper_trade
        self._exec: Execute | None = None
        self._last_second: dict[int, str] = {}

    def init_kite(self, access_token: str = None):
        """Initialize Kite connection and authentication."""
        self._kite = KiteConnect(api_key=self.api_key)
        if access_token:
            self._kite.set_access_token(access_token)
        else:
            print("Generate login url:", self._kite.login_url())
            req = input("Enter request token: ")
            sess = self._kite.generate_session(req, api_secret=self.api_secret)
            self._kite.set_access_token(sess["access_token"])
        
        # Create Execute instance with correct parameters
        self._exec = Execute(
            client=self._kite, 
            paper_trade=self._paper, 
            logger=self._logger
        )
        return self._exec

    def get_execute(self):
        """Get the Execute instance"""
        return self._exec

    def get_kite(self):
        return self._kite

    # BaseStreamer abstract methods implementation
    def _setup_connection(self):
        """Setup Kite ticker connection."""
        if not self._kite:
            raise RuntimeError("call init_kite() first")
        
        self._ticker = KiteTicker(self.api_key, self._kite.access_token)
        self._ticker.on_ticks = self._on_ticks
        self._ticker.on_connect = self._on_connect
        self._ticker.on_close = self._on_close
        self._ticker.on_error = self._on_error

    def _run_connection(self):
        """Run the ticker connection."""
        try:
            self._ticker.connect()
        except Exception as e:
            self._handle_connection_error(e)

    def _cleanup_connection(self):
        """Cleanup ticker connection."""
        if self._ticker:
            try:
                self._ticker.close()
            except Exception as e:
                self._logger.error(f"Error closing ticker: {e}")

    def _normalize_raw_data(self, raw_data: Dict[str, Any], symbol: str) -> QuoteEvent:
        """Normalize Zerodha tick data to QuoteEvent."""
        return QuoteNormalizer.normalize_zerodha_tick(
            raw_data, symbol, self.name
        )

    # Kite-specific event handlers
    def _on_ticks(self, ws, ticks):
        """Handle incoming ticks from Kite."""
        for t in ticks:
            tok = t['instrument_token']
            if tok not in self.symbols:
                continue

            try:
                # Use the base class method for processing
                self._process_raw_quote(t, str(tok))
                
            except Exception as e:
                self._logger.error(f"Error processing tick: {e}")

    def _on_connect(self, ws, response):
        """Handle ticker connection."""
        self._logger.info("Ticker connected. Subscribing to symbols ...")
        ws.subscribe(self.symbols)
        ws.set_mode(ws.MODE_FULL, self.symbols)

    def _on_close(self, ws, code, reason):
        """Handle ticker disconnection."""
        self._logger.warning(f"Ticker closed: {code} {reason}")
        self._is_running = False

    def _on_error(self, ws, code, reason):
        """Handle ticker errors."""
        self._logger.error(f"Ticker error: {code} {reason}")
        self._handle_connection_error(Exception(f"Ticker error: {code} {reason}"))
        ws.subscribe(self.symbols)
        ws.set_mode(ws.MODE_FULL, self.symbols)

    def _on_close(self, ws, code, reason):
        """Handle ticker disconnection."""
        self._logger.warning(f"Ticker closed: {code} {reason}")
        self._is_running = False

    def _on_error(self, ws, code, reason):
        """Handle ticker errors."""
        self._logger.error(f"Ticker error: {code} {reason}")
        self._handle_connection_error(Exception(f"Ticker error: {code} {reason}"))
