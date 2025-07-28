"""Simplified CandleMaker producing 5-minute VWAP candles."""
import csv
from datetime import datetime
from collections import defaultdict
from src.logger_factory import get_logger
import os

import matplotlib.pyplot as plt
import pandas as pd

DATA_CANDLE_DIR = "data/candles"
DATA_GRAPH_DIR = "data/graphs"
os.makedirs(DATA_CANDLE_DIR, exist_ok=True)
os.makedirs(DATA_GRAPH_DIR, exist_ok=True)

class CandleMaker:
    def __init__(self, csv_file: str = None):
        if csv_file is None:
            csv_file = os.path.join(DATA_CANDLE_DIR, "candles.csv")
        self._csv_file = csv_file
        self._handlers = []     # List of callbacks to notify on new candles
        self._current: dict = {}
        self._vwap_data = defaultdict(lambda: {"cum_tp_vol": 0.0, "cum_vol": 0.0})
        self._logger = get_logger("CandleMaker")

        # ensure header
        if not os.path.exists(self._csv_file):
            with open(self._csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "inst", "name", "open", "high", "low", "close", "volume", "vwap"])

        self._logger.info(f"CandleMaker initialized, writing to {self._csv_file}")
        self._logger.info("writing with header: timestamp, inst, name, open, high, low, close, volume, vwap")

    # ------------------------------------------------------------------
    def register_handler(self, cb):
        if callable(cb):
            self._logger.debug(f"Registering handler {cb.__name__}")
            self._handlers.append(cb)

    # ------------------------------------------------------------------
    def handle_quote_to_candle(self, quote: dict):
        self._logger.debug(f"Handling quote: {quote}")
        ts: datetime = quote['ts']
        inst = quote['inst']
        name = quote['name']
        ltp = quote['ltp']
        vol = quote.get('ltq') or quote.get('last_quantity') or quote.get('volume') or 0

        candle_time = ts.replace(second=0, microsecond=0)
        candle_time = candle_time.replace(minute=(candle_time.minute // 5) * 5)

        current = self._current.get(inst)

        if current is None or current['timestamp'] != candle_time:
            if current:
                self._logger.debug(f"Finalizing candle for {inst} at {current['timestamp']}")
                self._finalize(inst, current)
                self._logger.debug(f"Creating new candle for {inst} at {candle_time}")
            current = {
                'timestamp': candle_time,
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
                'volume': vol,
                'name': name,
            }
        else:
            current['high'] = max(current['high'], ltp)
            current['low'] = min(current['low'], ltp)
            current['close'] = ltp
            current['volume'] += vol

        self._vwap_data[inst]['cum_tp_vol'] += ltp * vol
        self._vwap_data[inst]['cum_vol'] += vol
        self._current[inst] = current

    # ------------------------------------------------------------------
    def _finalize(self, inst, candle):
        cum_tp_vol = self._vwap_data[inst]['cum_tp_vol']
        cum_vol = self._vwap_data[inst]['cum_vol']
        vwap = round(cum_tp_vol / cum_vol, 2) if cum_vol else None
        candle['vwap'] = vwap

        # Write to CSV
        with open(self._csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                candle['timestamp'].isoformat(),
                inst,
                candle['name'],
                candle['open'],
                candle['high'],
                candle['low'],
                candle['close'],
                candle['volume'],
                vwap,
            ])

        self._logger.info(f"Finalized candle for {inst} at {candle['timestamp']}")

        # notify handlers (e.g., strategy)
        for cb in self._handlers:
            cb(candle['name'], candle)

    # ------------------------------------------------------------------
    def reset_vwap(self, inst):
        """Reset VWAP tracking for a new session if needed."""
        self._logger.info(f"Resetting VWAP for {inst}")
        self._vwap_data[inst] = {"cum_tp_vol": 0.0, "cum_vol": 0.0}
