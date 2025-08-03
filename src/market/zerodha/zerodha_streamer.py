"""Live Zerodha ticker to quote handler pipeline."""
from datetime import datetime
import threading
import time
from typing import Callable, List

from kiteconnect import KiteConnect, KiteTicker

from src.logger_factory import get_logger
from src.core.executioner import Execute
from src.core.event_bus import Publisher, QuoteReceived

class ZerodhaStreamer(Publisher):
    def __init__(
        self,
        symbols: List[int],
        *,
        api_key: str,
        api_secret: str,
        name_symbol: str,
        paper_trade: bool = True,
    ):
        super().__init__()
        self.symbols = symbols
        self.api_key = api_key
        self.api_secret = api_secret
        self.name_symbol = name_symbol
        self._logger = get_logger("ZerodhaStreamer")
        self._kite: KiteConnect | None = None
        self._ticker: KiteTicker | None = None
        self._paper = paper_trade
        self._exec: Execute | None = None
        self._last_second: dict[int, str] = {}

    # ------------------------------------------------------------------
    def init_kite(self, access_token: str = None):
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

    # ------------------------------------------------------------------
    def get_execute(self):
        """Get the Execute instance"""
        return self._exec

    # ------------------------------------------------------------------
    def get_kite(self):
        return self._kite

    # ------------------------------------------------------------------
    def _on_ticks(self, ws, ticks):
        for t in ticks:
            tok = t['instrument_token']
            if tok not in self.symbols:
                continue

            # Store the complete tick as received
            try:
                from .quote_database import QuoteDatabase
                db = QuoteDatabase()
                db.save_quote(t)  # Save the full tick dictionary
            except Exception as e:
                self._logger.error(f"Failed to save quote to database: {e}")

            # Publish quote event
            ts = t.get('timestamp') or t.get('exchange_timestamp') or datetime.now()
            quote_event = QuoteReceived(
                timestamp=ts,
                source=self.__class__.__name__,
                symbol=self.name_symbol,
                instrument=tok,
                ltp=t.get('last_price', 0),
                volume=t.get('volume', 0),
                last_quantity=t.get('last_quantity', 0),
                change=t.get('change', 0),
                raw_data=t
            )
            self.publish_event(quote_event)

    def _on_connect(self, ws, response):
        self._logger.info("Ticker connected. Subscribing to symbols ...")
        ws.subscribe(self.symbols)
        ws.set_mode(ws.MODE_FULL, self.symbols)

    def _on_close(self, ws, code, reason):
        self._logger.warning(f"Ticker closed: {code} {reason}")
        ws.stop()

    def start(self):
        if not self._kite:
            raise RuntimeError("call init_kite() first")
        self._ticker = KiteTicker(self.api_key, self._kite.access_token)
        self._ticker.on_ticks = self._on_ticks
        self._ticker.on_connect = self._on_connect
        self._ticker.on_close = self._on_close
        self._logger.info("Starting ticker thread ...")
        threading.Thread(target=self._ticker.connect, daemon=True).start()
            raise RuntimeError("call init_kite() first")
        self._ticker = KiteTicker(self.api_key, self._kite.access_token)
        self._ticker.on_ticks = self._on_ticks
        self._ticker.on_connect = self._on_connect
        self._ticker.on_close = self._on_close
        self._logger.info("Starting ticker thread ...")
        threading.Thread(target=self._ticker.connect, daemon=True).start()
