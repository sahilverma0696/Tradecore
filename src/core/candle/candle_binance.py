"""CandleBinance: Aggregates Binance ticks into 1m/5m candles and computes VWAP."""
import csv
from datetime import datetime
from collections import defaultdict
from src.logger_factory import get_logger
import os
import traceback
from src.core.plotting.live_chart_server import LiveChartServer
from src.core.event_bus import Publisher, Subscriber, QuoteReceived, CandleGenerated

DATA_CANDLE_DIR = "data/candles"
os.makedirs(DATA_CANDLE_DIR, exist_ok=True)

class CandleBinance(Publisher, Subscriber):
    def __init__(self, csv_file: str = None):
        super().__init__()
        if csv_file is None:
            csv_file = os.path.join(DATA_CANDLE_DIR, "candles_binance.csv")
        self._csv_file = csv_file
        self._current = {}
        self._vwap_data = defaultdict(lambda: {"cum_tp_vol": 0.0, "cum_vol": 0.0})
        self._logger = get_logger("CandleBinance")

        if not os.path.exists(self._csv_file):
            with open(self._csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "symbol", "name", "open", "high", "low", "close", "volume", "vwap"])

        self._logger.info(f"CandleBinance initialized with event bus, writing to {self._csv_file}")
        
        # Subscribe to normalized quote events from Binance streamer
        self.subscribe_to_event(QuoteReceived, self._on_quote_event)

    def _on_quote_event(self, event: QuoteReceived):
        """Handle normalized quote events from event bus."""
        self._logger.debug(f"Handling Binance quote event: {event.symbol} @ {event.ltp}")
        
        # Only process Binance events (can filter by source if needed)
        if not event.source.lower().startswith('binance'):
            return
            
        ts = event.timestamp
        symbol = event.instrument
        name = event.symbol
        ltp = event.ltp
        vol = event.volume or 0

        candle_time = ts.replace(second=0, microsecond=0)
        candle_time = candle_time.replace(minute=(candle_time.minute // 5) * 5)

        current = self._current.get(symbol)
        if current is None or current['timestamp'] != candle_time:
            if current:
                self._logger.debug(f"Finalizing candle for {symbol} at {current['timestamp']}")
                self._finalize(symbol, current)
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

        self._vwap_data[symbol]['cum_tp_vol'] += ltp * vol
        self._vwap_data[symbol]['cum_vol'] += vol
        self._current[symbol] = current

    def register_plotting_handler(self):
        self._chart_server = LiveChartServer()
        
        def plotting_handler(event: CandleGenerated):
            # Only plot Binance candles
            if event.source == self.__class__.__name__:
                self._chart_server.add_candle(event.symbol, event.candle_data)
        
        self.subscribe_to_event(CandleGenerated, plotting_handler)
        self._chart_server.start_server()

    def _finalize(self, symbol, candle):
        cum_tp_vol = self._vwap_data[symbol]['cum_tp_vol']
        cum_vol = self._vwap_data[symbol]['cum_vol']
        vwap = round(cum_tp_vol / cum_vol, 2) if cum_vol else None
        candle['vwap'] = vwap

        with open(self._csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                candle['timestamp'].isoformat(),
                symbol,
                candle['name'],
                candle['open'],
                candle['high'],
                candle['low'],
                candle['close'],
                candle['volume'],
                vwap,
            ])

        self._logger.info(f"Finalized Binance candle for {symbol} at {candle['timestamp']} with VWAP {candle['vwap']}")
        
        # Publish candle event to event bus
        candle_event = CandleGenerated(
            timestamp=candle['timestamp'],
            source=self.__class__.__name__,
            symbol=candle['name'],
            candle_data=candle,
            timeframe="5m"
        )
        self.publish_event(candle_event)

    def reset_vwap(self, symbol):
        self._logger.info(f"Resetting VWAP for {symbol}")
        self._vwap_data[symbol] = {"cum_tp_vol": 0.0, "cum_vol": 0.0}
    def reset_vwap(self, symbol):
        self._logger.info(f"Resetting VWAP for {symbol}")
        self._vwap_data[symbol] = {"cum_tp_vol": 0.0, "cum_vol": 0.0}
