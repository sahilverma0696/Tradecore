"""Demo data generator — writes IPC files so the dashboard can display simulated trades."""

import os
import json
import time
import math
import random
from datetime import datetime

_SYMBOLS = ["NIFTY", "BANKNIFTY", "BTCUSDT"]
_BASE_PRICES = {"NIFTY": 18500.0, "BANKNIFTY": 42000.0, "BTCUSDT": 65000.0}

_QUOTE_FILE = "data/live_quotes.json"
_CANDLE_FILE = "data/live_candles.json"
_ORDER_FILE = "data/live_order.json"


def _atomic_write(path: str, data):
    os.makedirs("data", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


class DemoDataGenerator:
    def __init__(self):
        self._prices = _BASE_PRICES.copy()
        self._candles: dict = {}
        self._orders: dict = {}
        self._vwap_state: dict = {s: {"cum_tp_vol": 0.0, "cum_vol": 0.0} for s in _SYMBOLS}
        self._tick = 0
        self.running = False

    def start(self):
        self.running = True
        while self.running:
            self._tick += 1
            self._step_prices()
            self._write_quotes()
            if self._tick % 10 == 0:
                self._close_candles()
            self._maybe_open_order()
            self._update_orders()
            self._write_orders()
            time.sleep(0.5)

    def stop(self):
        self.running = False

    def _step_prices(self):
        for sym in _SYMBOLS:
            drift = math.sin(self._tick * 0.05) * 0.001
            noise = random.gauss(0, 0.002)
            self._prices[sym] *= (1 + drift + noise)

            ltp = self._prices[sym]
            ltq = random.uniform(1, 50)
            vd = self._vwap_state[sym]
            vd["cum_tp_vol"] += ltp * ltq
            vd["cum_vol"] += ltq

            if sym not in self._candles:
                self._candles[sym] = {"open": ltp, "high": ltp, "low": ltp, "close": ltp,
                                      "volume": 0.0, "timestamp": datetime.now().isoformat()}
            c = self._candles[sym]
            c["high"] = max(c["high"], ltp)
            c["low"] = min(c["low"], ltp)
            c["close"] = ltp
            c["volume"] += ltq
            vwap = vd["cum_tp_vol"] / vd["cum_vol"] if vd["cum_vol"] else ltp
            c["vwap"] = round(vwap, 4)
            c["timeframe"] = "3"

    def _write_quotes(self):
        now = datetime.now().isoformat()
        data = {
            sym: {"ltp": round(self._prices[sym], 4), "ltq": round(random.uniform(1, 50), 2),
                  "source": "DemoStreamer", "timestamp": now}
            for sym in _SYMBOLS
        }
        _atomic_write(_QUOTE_FILE, data)

    def _close_candles(self):
        data = {}
        for sym, c in self._candles.items():
            data[sym] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items()}
        _atomic_write(_CANDLE_FILE, data)
        for sym in _SYMBOLS:
            ltp = self._prices[sym]
            self._candles[sym] = {"open": ltp, "high": ltp, "low": ltp, "close": ltp,
                                  "volume": 0.0, "timestamp": datetime.now().isoformat(), "timeframe": "3"}

    def _maybe_open_order(self):
        if len(self._orders) >= 2:
            return
        for sym in _SYMBOLS:
            if sym not in self._orders and random.random() < 0.03:
                side = random.choice(["BUY", "SELL"])
                entry = self._prices[sym]
                trail = 0.03
                self._orders[sym] = {
                    "id": int(time.time()),
                    "symbol": sym, "instrument": sym, "side": side,
                    "total_quantity": random.choice([25, 50, 75]),
                    "entry_price": round(entry, 4),
                    "loss_stop": round(entry * (0.98 if side == "BUY" else 1.02), 4),
                    "zero_stop": 0.0, "net_stop": 0.0,
                    "trigger": trail * 100,
                    "entry_time": datetime.now().isoformat(),
                    "_side": side, "_entry": entry,
                }

    def _update_orders(self):
        to_close = []
        for sym, o in self._orders.items():
            ltp = self._prices[sym]
            entry = o["_entry"]
            side = o["_side"]
            pnl = (ltp - entry) if side == "BUY" else (entry - ltp)
            pnl_pct = pnl / entry * 100
            max_pct = max(0.0, pnl_pct)
            o.update({
                "current_ltp": round(ltp, 4),
                "current_profit": round(pnl * o["total_quantity"], 2),
                "current_profit_percentage": round(pnl_pct, 4),
                "max_move_percentage": round(max_pct, 4),
                "min_move_percentage": round(min(0.0, pnl_pct), 4),
                "retreat": round(max(0.0, max_pct - pnl_pct), 4),
                "last_update": datetime.now().isoformat(),
            })
            if abs(pnl_pct) > 3.0 or random.random() < 0.005:
                to_close.append(sym)
        for sym in to_close:
            del self._orders[sym]

    def _write_orders(self):
        orders = [{k: v for k, v in o.items() if not k.startswith("_")}
                  for o in self._orders.values()]
        _atomic_write(_ORDER_FILE, {"timestamp": datetime.now().isoformat(),
                                    "total_orders": len(orders), "orders": orders})


def start_demo_data_generator():
    gen = DemoDataGenerator()
    try:
        gen.start()
    except KeyboardInterrupt:
        gen.stop()


if __name__ == "__main__":
    start_demo_data_generator()
