from typing import Dict, Any
from src.core.event_bus import Subscriber, Publisher, CandleGenerated, EntrySignal
from src.core.event_bus.events import OrderEvent
from src.logger_factory import get_logger


class VwapStrategy(Subscriber, Publisher):
    """VWAP cross strategy — publishes EntrySignal on candle close crossing VWAP."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__()
        self.config = config or {}
        self.logger = get_logger("VwapStrategy", console_output=True)
        self.positions: Dict[str, dict] = {}

        self.subscribe_to_event(CandleGenerated, self.on_candle_generated)
        self.subscribe_to_event(OrderEvent, self._on_order_event)
        self.logger.info("VwapStrategy initialized")

    def on_candle_generated(self, event: CandleGenerated):
        try:
            self.process_candle(event)
        except Exception as e:
            self.logger.error(f"Error processing candle for {event.symbol}: {e}")

    def process_candle(self, event: CandleGenerated):
        symbol = event.symbol
        vwap = event.vwap
        open_price = event.open
        close_price = event.close

        if vwap is None:
            self.logger.warning(f"VWAP missing in candle for {symbol} @ {event.timestamp}")
            return

        existing = self.positions.get(symbol)
        if open_price < vwap and close_price > vwap:
            if not existing or existing.get('side') != 'BUY':
                self._trigger_entry_signal(symbol, 'BUY', close_price, event, vwap)
        elif open_price > vwap and close_price < vwap:
            if not existing or existing.get('side') != 'SELL':
                self._trigger_entry_signal(symbol, 'SELL', close_price, event, vwap)

    def _trigger_entry_signal(self, symbol, side, price, event: CandleGenerated, vwap):
        self.positions[symbol] = {'symbol': symbol, 'side': side, 'entry_price': price, 'entry_vwap': vwap}
        self.publish_event(EntrySignal(
            timestamp=event.timestamp,
            source=self.__class__.__name__,
            symbol=symbol,
            direction=side,
            price=event.close,
            strategy="VWAPCross",
            candle=event,
        ))

    def _on_order_event(self, event: OrderEvent):
        if event.type in ('FULL', 'SWITCH') and event.instrument in self.positions:
            del self.positions[event.instrument]

    def get_active_positions(self) -> Dict[str, dict]:
        return self.positions
