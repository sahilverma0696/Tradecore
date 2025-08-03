"""Live Zerodha ticker to quote handler pipeline."""
from datetime import datetime
import threading
import time
from typing import Callable, List
import traceback

from kiteconnect import KiteConnect, KiteTicker

from src.logger_factory import get_logger
from src.execute.zerodha_executioner import ZerodhaExecute

class ZerodhaStreamer:
    def __init__(
        self,
        symbols: List[int],
        *,
        api_key: str,
        api_secret: str,
        name_symbol: str,
        paper_trade: bool = True,
    ):
        self.symbols = symbols
        self.api_key = api_key
        self.api_secret = api_secret
        self.name_symbol = name_symbol
        self._logger = get_logger("ZerodhaStreamer")
        self._kite: KiteConnect | None = None
        self._ticker: KiteTicker | None = None
        self._handlers: List[Callable[[dict], None]] = []
        self._paper = paper_trade
        self._exec: ZerodhaExecute | None = None
        self._last_second: dict[int, str] = {}

    # ------------------------------------------------------------------
    def register_handler(self, cb):
        if callable(cb):
            self._logger.debug(f"Registering handler {cb.__name__}")
            self._handlers.append(cb)

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
        self._exec = ZerodhaExecute(self._kite, paper_trade=self._paper, logger=self._logger)

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
                from ...data_store.quote_database import QuoteDatabase
                db = QuoteDatabase()
                db.save_quote(t)  # Save the full tick dictionary
            except Exception as e:
                self._logger.error(f"Failed to save quote to database: {e}")

            # Create compatibility quote with proper timestamp handling
            ts = t.get('timestamp') or t.get('exchange_timestamp') or datetime.now()
            
            # Ensure timestamp is a datetime object
            if not isinstance(ts, datetime):
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    except:
                        ts = datetime.now()
                elif hasattr(ts, 'timestamp'):
                    ts = datetime.fromtimestamp(ts.timestamp())
                else:
                    ts = datetime.now()
            
            compat_quote = {
                'ts': ts,
                'timestamp': ts,  # Add both for compatibility
                'inst': tok,
                'name': self.name_symbol,
                'ltp': t.get('last_price', 0),
                'last_quantity': t.get('last_quantity', 0),
                'volume': t.get('volume', 0),
                'change': t.get('change', 0),
                'oi': t.get('oi', 0),  # Open interest
                'ohlc': t.get('ohlc', {}),  # OHLC data
                'depth': t.get('depth', {})  # Market depth
            }
            
            for cb in self._handlers:
                try:
                    cb(compat_quote)
                except Exception as e:
                    self._logger.error(f"handler error: {e}\n{traceback.format_exc()}")

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
