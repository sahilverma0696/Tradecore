"""Simplified CandleMaker producing 5-minute VWAP candles with event bus."""
import csv
from datetime import datetime
from collections import defaultdict
from src.logger_factory import get_logger
import os
import traceback

import pandas as pd
from src.core.plotting.live_chart_server import LiveChartServer
from src.core.event_bus import Publisher, Subscriber, QuoteReceived, CandleGenerated

DATA_CANDLE_DIR = "data/candles"
DATA_GRAPH_DIR = "data/graphs"
os.makedirs(DATA_CANDLE_DIR, exist_ok=True)
os.makedirs(DATA_GRAPH_DIR, exist_ok=True)

class CandleMaker(Publisher, Subscriber):
    def __init__(self, csv_file: str = None):
        super().__init__()
        if csv_file is None:
            csv_file = os.path.join(DATA_CANDLE_DIR, "candles.csv")
        self._csv_file = csv_file
        self._current: dict = {}
        self._vwap_data = defaultdict(lambda: {"cum_tp_vol": 0.0, "cum_vol": 0.0})
        self._logger = get_logger("CandleMaker")

        # ensure header
        if not os.path.exists(self._csv_file):
            with open(self._csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "inst", "name", "open", "high", "low", "close", "volume", "vwap"])

        self._logger.info(f"CandleMaker initialized with event bus, writing to {self._csv_file}")
        
        # Subscribe to normalized quote events from streamers
        self.subscribe_to_event(QuoteReceived, self._on_quote_event)

    def _on_quote_event(self, event: QuoteReceived):
        """Handle normalized quote events from event bus."""
        self._logger.debug(f"Handling quote event: {event.symbol} @ {event.ltp}")
        
        ts = event.timestamp
        inst = event.instrument
        name = event.symbol
        ltp = event.ltp
        vol = event.last_quantity or event.volume or 0

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

        self._logger.info(f"Finalized candle for {inst} at {candle['timestamp']} with VWAP {candle['vwap']}")

        # Publish candle event to event bus
        candle_event = CandleGenerated(
            timestamp=candle['timestamp'],
            source=self.__class__.__name__,
            symbol=candle['name'],
            candle_data=candle,
            timeframe="5m"
        )
        self.publish_event(candle_event)

    def reset_vwap(self, inst):
        """Reset VWAP tracking for a new session if needed."""
        self._logger.info(f"Resetting VWAP for {inst}")
        self._vwap_data[inst] = {"cum_tp_vol": 0.0, "cum_vol": 0.0}

    def register_plotting_handler(self):
        """Initialize live chart server and subscribe to candle events."""
        self._chart_server = LiveChartServer()
        
        def plotting_handler(event: CandleGenerated):
            self._chart_server.add_candle(event.symbol, event.candle_data)
        
        self.subscribe_to_event(CandleGenerated, plotting_handler)
        self._chart_server.start_server()
        self.subscribe_to_event(CandleGenerated, plotting_handler)
        self._chart_server.start_server()
        self.register_handler(plotting_handler)
        self._chart_server.start_server()
        self.register_handler(plotting_handler)
