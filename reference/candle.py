import csv
from datetime import datetime
from collections import defaultdict
from logger_factory import get_logger
from quotes import QuoteStreamer

class CandleMaker:
    def __init__(self, csv_file="./logs/candles.csv"):
        """
        Aggregates quotes into 5-minute OHLCVW candles.
        """
        self.handlers = []
        self.csv_file = csv_file
        self.current_candles = {}
        self.vwap_data = defaultdict(lambda: {"cum_tp_vol": 0.0, "cum_vol": 0.0})
        self.logger = get_logger("candles")

        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'inst', 'name', 'open', 'high', 'low', 'close',
                'volume', 'vwap'
            ])
        self.logger.info(f"CandleMaker initialized. Writing candles to {self.csv_file}")

    def register_handler(self, handler_func):
        """
        Register a function to be called on finalized candle.
        Each handler: fn(name, candle_dict)
        """
        if callable(handler_func):
            self.handlers.append(handler_func)
            self.logger.info(f"Registered new candle handler: {handler_func.__name__}")

    def handle_quote(self, quote):
        ts = quote['ts']
        inst = quote['inst']
        name = quote['name']
        ltp = quote['ltp']
        volume = quote['ltq']

        # Normalize to 5-minute candle time
        candle_time = ts.replace(second=0, microsecond=0)
        minute = candle_time.minute - (candle_time.minute % 5)
        candle_time = candle_time.replace(minute=minute)

        current = self.current_candles.get(inst)

        # Finalize previous candle if needed
        if current is None or current['timestamp'] != candle_time:
            if current:
                self._finalize_candle(inst, current)
            candle = {
                'timestamp': candle_time,
                'open': ltp,
                'high': ltp,
                'low': ltp,
                'close': ltp,
                'volume': volume,
                'name': name
            }
            self.logger.debug(f"New candle started for {inst} at {candle_time}")
        else:
            candle = current
            candle['high'] = max(candle['high'], ltp)
            candle['low'] = min(candle['low'], ltp)
            candle['close'] = ltp
            candle['volume'] += volume
            self.logger.debug(f"Updated candle: ts={ts}, ltp={ltp}, vol={volume}")

        # Update cumulative VWAP data (session-wide)
        self.vwap_data[inst]['cum_tp_vol'] += ltp * volume
        self.vwap_data[inst]['cum_vol'] += volume

        self.current_candles[inst] = candle

    def _finalize_candle(self, inst, candle):
        """
        Finalize the candle, calculate session VWAP, write CSV, and notify handlers.
        """
        cum_tp_vol = self.vwap_data[inst]['cum_tp_vol']
        cum_vol = self.vwap_data[inst]['cum_vol']
        vwap = round(cum_tp_vol / cum_vol, 2) if cum_vol > 0 else None

        candle['vwap'] = vwap

        # Write to CSV
        with open(self.csv_file, 'a', newline='') as f:
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
                vwap
            ])

        self.logger.info(
            f"Finalized candle for {inst} at {candle['timestamp']}: "
            f"O:{candle['open']} H:{candle['high']} L:{candle['low']} C:{candle['close']} "
            f"V:{candle['volume']} VWAP:{vwap}"
        )

        # Notify all handlers
        for handler in self.handlers:
            try:
                handler(candle['name'], candle)
            except Exception as e:
                self.logger.error(f"Error in candle handler {handler.__name__}: {e}")
