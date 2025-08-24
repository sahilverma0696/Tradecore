import csv
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional, Any
from src.core.event_bus import Subscriber, Publisher, CandleGenerated, EntrySignal, ExitSignal
from src.logger_factory import get_logger


class VwapStrategy(Subscriber, Publisher):
    """VWAP cross strategy with integrated exit management."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()  # Initialize both mixins
        self.config = config or {}
        self.logger = get_logger("VwapStrategy", console_output=True)
        self.default_quantity = self.config.get('default_quantity', 75)
        self.exit_steps = self.config.get('exit_steps', [])
        self.positions: Dict[str, dict] = {}
        self.logger.info("VWAPStrategy initialized with event bus.")
        
        # Subscribe to candle events
        self.subscribe_to_event(CandleGenerated, self.on_candle_generated)
        self.logger.info(f"✅ VwapStrategy subscribed to CandleGenerated events")

    def on_candle_generated(self, event: CandleGenerated):
        """Handle new candle events and generate trading signals."""
        try:
            self.logger.info(f"💡 Received candle for {event.symbol}: Close={event.close}, VWAP={event.vwap}")
            
            # Process candle and generate signals
            self.process_candle(event)
            
        except Exception as e:
            self.logger.error(f"Error processing candle for {event.symbol}: {e}")

    def process_candle(self, event: CandleGenerated):
        symbol = event.symbol
        candle = event.candle_data
        vwap = candle.get('vwap')
        open_price = candle['open']
        close_price = candle['close']

        if vwap is None:
            self.logger.warning(f"VWAP missing in candle for {symbol} @ {candle['timestamp']}")
            return

        if symbol in self.positions:
            return  # Only generate one entry per symbol

        # Entry logic - publish entry signal event
        if open_price < vwap and close_price > vwap:
            self._trigger_entry_signal(symbol, 'BUY', close_price, candle, vwap)
        elif open_price > vwap and close_price < vwap:
            self._trigger_entry_signal(symbol, 'SELL', close_price, candle, vwap)

    def _trigger_entry_signal(self, symbol, side, price, candle, vwap):
        entry_signal_data = {
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
        self.positions[symbol] = entry_signal_data
        self.logger.info(f"[ENTRY SIGNAL] {side} {symbol} @ {price} VWAP={vwap}")
        
        # Publish entry signal event
        entry_event = EntrySignal(
            timestamp=candle['timestamp'],
            source=self.__class__.__name__,
            symbol=symbol,
            side=side,
            entry_price=price,
            entry_vwap=vwap,
            quantity=self.default_quantity,
            exit_steps=self.exit_steps,
            strategy_name=self.__class__.__name__,
            candle_data=candle
        )
        self.publish_event(entry_event)

    def get_active_positions(self) -> Dict[str, dict]:
        return self.positions
