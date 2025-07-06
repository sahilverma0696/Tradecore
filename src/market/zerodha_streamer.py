"""Live Zerodha ticker to quote handler pipeline."""
from datetime import datetime
import threading
import time
from typing import Callable, List

from kiteconnect import KiteConnect, KiteTicker

from src.logger_factory import get_logger
from src.core.executioner import Executioner

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
        self._exec: Executioner | None = None
        self._last_second: dict[int, str] = {}

    # ------------------------------------------------------------------
    def register_handler(self, cb):
        if callable(cb):
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
        self._exec = Executioner(self._kite, paper_trade=self._paper, logger=self._logger)

    # ------------------------------------------------------------------
    def get_kite(self):
        return self._kite

    # ------------------------------------------------------------------
    def _on_ticks(self, ws, ticks):
        for t in ticks:
            tok = t['instrument_token']
            if tok not in self.symbols:
                continue
                
            # Create a comprehensive quote dictionary with all available fields
            ts = t.get('timestamp') or t.get('exchange_timestamp') or datetime.now()
            quote = {
                'instrument_token': tok,
                'timestamp': ts,
                'mode': t.get('mode'),
                'volume': t.get('volume'),
                'last_price': t.get('last_price'),
                'average_price': t.get('average_price'),
                'last_quantity': t.get('last_quantity'),
                'buy_quantity': t.get('buy_quantity'),
                'sell_quantity': t.get('sell_quantity'),
                'change': t.get('change'),
                'last_trade_time': t.get('last_trade_time'),
                'ohlc': t.get('ohlc'),
                'depth': t.get('depth')
            }
            
            # Also include the original format for backward compatibility
            compat_quote = {
                'ts': ts,
                'inst': tok,
                'name': self.name_symbol,
                'ltp': t.get('last_price'),
                'last_quantity': t.get('last_quantity', 0),
                'volume': t.get('volume', 0),
                'change': t.get('change')
            }
            
            # Call all registered handlers with the compatibility quote
            for cb in self._handlers:
                try:
                    cb(compat_quote)
                except Exception as e:
                    self._logger.error(f"handler error: {e}")
                    
            # Store the full quote in the database
            try:
                from .quote_database import QuoteDatabase
                db = QuoteDatabase()
                db.save_quote(quote)
            except Exception as e:
                self._logger.error(f"Failed to save quote to database: {e}")

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
