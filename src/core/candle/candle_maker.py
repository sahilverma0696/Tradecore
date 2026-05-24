import csv
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any
import os
from src.logger_factory import get_logger
from src.system_config_manager import SystemConfigManager
from src.core.event_bus.mixins import Publisher, Subscriber
from src.core.event_bus.events import QuoteEvent, CandleGenerated

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
        self.system_config = SystemConfigManager()
        self.timeframe = self.system_config.get("candle_maker.default_timeframe")

        # ensure header
        if not os.path.exists(self._csv_file):
            with open(self._csv_file, 'w', newline='') as f:
                csv.writer(f).writerow(["timestamp", "symbol", "open", "high", "low", "close", "volume", "vwap"])

        self._logger.info(f"CandleMaker initialized with event bus, writing to {self._csv_file}")
        
        # Subscribe to normalized quote events from streamers
        self.subscribe_to_event(QuoteEvent, self._on_quote_event)

    def _on_quote_event(self, event: QuoteEvent):
        """Handle incoming quote events and build candles."""
        # self._logger.debug(f"Handling quote event: {event.instrument} @ {event.ltp}")
        
        symbol = event.instrument
        timestamp = event.timestamp
        price = event.ltp
        volume = event.ltq or 0

        candle_time = timestamp.replace(second=0, microsecond=0)
        candle_time = candle_time.replace(minute=(candle_time.minute // self.timeframe) * self.timeframe)

        current = self._current.get(symbol)

        if current is None or current['timestamp'] != candle_time:
            if current:
                # self._logger.debug(f"Finalizing candle for {symbol} at {current['timestamp']}")
                self._finalize(symbol, current)
                self._logger.debug(f"Creating new candle for {symbol} at {candle_time}")
            current = {
                'timestamp': candle_time,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume,
                'name': symbol,
            }
        else:
            current['high'] = max(current['high'], price)
            current['low'] = min(current['low'], price)
            current['close'] = price
            current['volume'] += volume

        # Calculate VWAP
        self._vwap_data[symbol]['cum_tp_vol'] += price * volume
        self._vwap_data[symbol]['cum_vol'] += volume
        
        if self._vwap_data[symbol]['cum_vol'] > 0:
            current['vwap'] = self._vwap_data[symbol]['cum_tp_vol'] / self._vwap_data[symbol]['cum_vol']
        else:
            current['vwap'] = price
            
        self._current[symbol] = current

    def _finalize(self, symbol: str, candle: Dict[str, Any]):
        """Finalize and publish a completed candle."""
        try:
            # self._logger.debug(f"Finalizing candle for {symbol}: {candle}")
            
            # Create CandleGenerated event with all required parameters including source
            candle_event = CandleGenerated(
                timestamp=candle['timestamp'],
                symbol=symbol,
                timeframe=str(self.timeframe),
                open=candle['open'],
                high=candle['high'],
                low=candle['low'],
                close=candle['close'],
                volume=candle['volume'],
                vwap=candle.get('vwap'),
                source="CandleMaker"  # Add missing source parameter
            )
            
            self.publish_event(candle_event)
            self._logger.info(f"Published candle for {symbol}: O={candle['open']:.2f} H={candle['high']:.2f} L={candle['low']:.2f} C={candle['close']:.2f} V={candle['volume']:.2f} VWAP={candle['vwap']:.2f}")
            
            # Write to CSV
            self._write_to_csv(candle)
            
        except Exception as e:
            self._logger.error(f"Error finalizing candle for {symbol}: {e}")

    def _write_to_csv(self, candle: Dict[str, Any]):
        """Write candle data to CSV file."""
        try:
            with open(self._csv_file, 'a', newline='') as f:
                csv.writer(f).writerow([
                    candle['timestamp'],
                    candle.get('name', ''),
                    candle['open'],
                    candle['high'],
                    candle['low'],
                    candle['close'],
                    candle['volume'],
                    candle.get('vwap', 0.0),
                ])
        except Exception as e:
            self._logger.error(f"Error writing candle to CSV: {e}")

    def reset_vwap(self, inst):
        """Reset VWAP tracking for a new session if needed."""
        self._logger.info(f"Resetting VWAP for {inst}")
        self._vwap_data[inst] = {"cum_tp_vol": 0.0, "cum_vol": 0.0}

