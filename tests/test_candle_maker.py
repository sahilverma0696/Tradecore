import os
import tempfile
import unittest
from datetime import datetime
from src.core.candle.candle_maker import CandleMaker
from src.core.event_bus import EventBus, CandleGenerated
from src.core.event_bus.events import QuoteEvent


class TestCandleMaker(unittest.TestCase):
    def setUp(self):
        EventBus._instance = None
        self._tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        self._tmp.close()

    def tearDown(self):
        EventBus._instance = None
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def _make_quote(self, symbol, ltp, ltq=10.0, minute=15):
        return QuoteEvent(
            timestamp=datetime(2023, 1, 1, 9, minute, 0),
            source="TestStreamer",
            instrument=symbol,
            name=symbol,
            ltp=ltp,
            ltq=ltq,
        )

    def test_candle_published_on_timeframe_boundary(self):
        """Ticks within one candle period accumulate; crossing the boundary publishes the prior candle."""
        received = []
        event_bus = EventBus()
        event_bus.subscribe(CandleGenerated, received.append)

        cm = CandleMaker(csv_file=self._tmp.name)

        # Two ticks in the 9:15 candle (minute 15, tf=3 → bucket 9:15)
        event_bus.publish(self._make_quote("TESTSYM", 100.0, minute=15))
        event_bus.publish(self._make_quote("TESTSYM", 102.0, minute=16))
        # First tick in the next candle period (9:18) — triggers finalize of 9:15
        event_bus.publish(self._make_quote("TESTSYM", 105.0, minute=18))

        self.assertEqual(len(received), 1)
        c = received[0]
        self.assertEqual(c.symbol, "TESTSYM")
        self.assertAlmostEqual(c.open, 100.0)
        self.assertAlmostEqual(c.close, 102.0)
        self.assertAlmostEqual(c.high, 102.0)
        self.assertAlmostEqual(c.low, 100.0)

    def test_vwap_calculated(self):
        """VWAP = cumulative (price × volume) / cumulative volume."""
        received = []
        EventBus().subscribe(CandleGenerated, received.append)

        cm = CandleMaker(csv_file=self._tmp.name)
        event_bus = EventBus()
        event_bus.publish(self._make_quote("A", 100.0, ltq=10.0, minute=15))
        event_bus.publish(self._make_quote("A", 200.0, ltq=10.0, minute=16))
        # Trigger finalize
        event_bus.publish(self._make_quote("A", 150.0, ltq=5.0, minute=18))

        self.assertEqual(len(received), 1)
        expected_vwap = (100 * 10 + 200 * 10) / 20
        self.assertAlmostEqual(received[0].vwap, expected_vwap, places=4)

    def test_multiple_symbols_independent(self):
        """Each symbol maintains its own candle independently."""
        received = []
        EventBus().subscribe(CandleGenerated, received.append)

        cm = CandleMaker(csv_file=self._tmp.name)
        bus = EventBus()
        for sym in ("SYM1", "SYM2"):
            bus.publish(self._make_quote(sym, 100.0, minute=15))
        for sym in ("SYM1", "SYM2"):
            bus.publish(self._make_quote(sym, 101.0, minute=18))  # triggers finalize for both

        symbols = {c.symbol for c in received}
        self.assertEqual(symbols, {"SYM1", "SYM2"})


if __name__ == "__main__":
    unittest.main()
