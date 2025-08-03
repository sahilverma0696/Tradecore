import csv
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
from src.logger_factory import get_logger


# class IncrementalVWAP:
#     def __init__(self):
#         self.cum_pv = 0.0  # Cumulative price * volume
#         self.cum_vol = 0.0
#         self.vwap = None

#     def update(self, high: float, low: float, close: float, volume: float) -> float:
#         # VWAP = sum(close * volume) / sum(volume)
#         self.cum_pv += close * volume
#         self.cum_vol += volume

#         if self.cum_vol > 0:
#             self.vwap = round(self.cum_pv / self.cum_vol, 2)
#         return self.vwap

#     def update_from_quote(self, ltp: float, volume: float) -> float:
#         # For tick data, use ltp * volume
#         self.cum_pv += ltp * volume
#         self.cum_vol += volume

#         if self.cum_vol > 0:
#             self.vwap = round(self.cum_pv / self.cum_vol, 2)
#         return self.vwap

class VwapStrategy:
    """VWAP cross strategy. This class generates only entry signals."""

    def __init__(self, config: dict = None):
        self._logger = get_logger("VWAPStrategy")
        config = config or {}
        self.default_quantity = config.get('default_quantity', 75)
        self.positions: Dict[str, dict] = {}
        self._handlers = []  # Entry signal handlers
        self._logger.info("VWAPStrategy (Entry-only) initialized.")

    def register_handler(self, cb):
        """Register a callback for entry signals."""
        if callable(cb):
            self._handlers.append(cb)

    def on_candle(self, symbol: str, candle: dict):
        vwap = candle.get('vwap')
        open_price = candle['open']
        close_price = candle['close']

        if vwap is None:
            self._logger.warning(f"VWAP missing in candle for {symbol} @ {candle['timestamp']}")
            return

        if symbol in self.positions:
            return  # Only generate one entry per symbol

        # Entry logic
        if open_price < vwap and close_price > vwap:
            self._trigger_entry(symbol, 'BUY', close_price, candle, vwap)
        elif open_price > vwap and close_price < vwap:
            self._trigger_entry(symbol, 'SELL', close_price, candle, vwap)

    def _trigger_entry(self, symbol, side, price, candle, vwap):
        entry = {
            'symbol': symbol,
            'side': side,
            'entry_price': price,
            'entry_time': candle['timestamp'],
            'name': candle.get('name', symbol),
            'entry_open': candle['open'],
            'entry_close': candle['close'],
            'entry_vwap': vwap,
            'quantity': self.default_quantity,
        }
        self.positions[symbol] = entry
        self._logger.info(f"[ENTRY] {side} {symbol} @ {price} VWAP={vwap}")
        for cb in self._handlers:
            # Pass all relevant info for order creation
            cb(
                signal="ENTER",
                instrument=symbol,
                candle=candle,
                side=side,
                step=None,
                trail=None,
                quantity=self.default_quantity,
                timestamp=candle['timestamp']
            )

    def get_active_positions(self) -> Dict[str, dict]:
        return self.positions
