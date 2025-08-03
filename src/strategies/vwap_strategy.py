import csv
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
from src.logger_factory import get_logger


class VwapStrategy:
    """VWAP cross strategy with integrated exit management."""

    def __init__(self, config: dict = None):
        self._logger = get_logger("VWAPStrategy")
        config = config or {}
        self.default_quantity = config.get('default_quantity', 75)
        self.exit_steps = config.get('exit_steps', [])
        self.positions: Dict[str, dict] = {}
        self._handlers = []  # Entry signal handlers
        self._logger.info("VWAPStrategy initialized.")

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

        # Entry logic - send signal to OrderManager
        if open_price < vwap and close_price > vwap:
            self._trigger_entry_signal(symbol, 'BUY', close_price, candle, vwap)
        elif open_price > vwap and close_price < vwap:
            self._trigger_entry_signal(symbol, 'SELL', close_price, candle, vwap)

    def _trigger_entry_signal(self, symbol, side, price, candle, vwap):
        entry_signal = {
            'signal': 'ENTER',
            'symbol': symbol,
            'side': side,
            'entry_price': price,
            'entry_time': candle['timestamp'],
            'name': candle.get('name', symbol),
            'entry_vwap': vwap,
            'quantity': self.default_quantity,
            'steps': self.exit_steps,
            'candle': candle
        }
        self.positions[symbol] = entry_signal
        self._logger.info(f"[ENTRY SIGNAL] {side} {symbol} @ {price} VWAP={vwap}")
        
        # Send signal to OrderManager
        for cb in self._handlers:
            cb(entry_signal)

    def get_active_positions(self) -> Dict[str, dict]:
        return self.positions
