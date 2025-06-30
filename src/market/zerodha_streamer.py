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
    def start(self):
        self._ticker = KiteTicker(self.api_key, self._kite.access_token)

        def on_ticks(ws, ticks):
            for t in ticks:
                tok = t['instrument_token']
                if tok not in self.symbols:
                    continue
                price = float(t['last_price'])
                ts = t.get('exchange_timestamp') or datetime.now()
                quote = {
                    'ts': ts,
                    'inst': tok,
                    'name': self.name_symbol,
                    'ltp': price,
                    'ltq': t.get('last_quantity', 0),
                    'cp': t.get('change', None),
                }
                for cb in self._handlers:
                    cb(quote)
        def on_connect(ws, _):
            ws.subscribe(self.symbols)
            ws.set_mode(ws.MODE_FULL, self.symbols)
        self._ticker.on_ticks = on_ticks
        self._ticker.on_connect = on_connect
        threading.Thread(target=self._ticker.connect, daemon=True).start()
