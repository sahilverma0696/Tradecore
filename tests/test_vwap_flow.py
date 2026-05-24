import unittest
from datetime import datetime

from src.strategies.vwap_strategy import VwapStrategy
from src.core.order_manager import OrderManager
from src.core.event_bus import EventBus, EntrySignal, CandleGenerated
from src.core.executors.executor_factory import ExecutorFactory


def _candle(symbol="TEST", open_p=100.0, close_p=103.0, vwap=101.0):
    return CandleGenerated(
        timestamp=datetime.now(),
        source="TestCandleMaker",
        symbol=symbol,
        timeframe="3",
        open=open_p,
        high=max(open_p, close_p) + 0.5,
        low=min(open_p, close_p) - 0.5,
        close=close_p,
        volume=1000,
        vwap=vwap,
    )


class TestVWAPFlow(unittest.TestCase):
    def setUp(self):
        EventBus._instance = None
        self.strategy = VwapStrategy()
        self.order_mgr = OrderManager()

    def tearDown(self):
        EventBus._instance = None

    def test_vwap_cross_buy_generates_entry_signal(self):
        """open < vwap and close > vwap → BUY EntrySignal."""
        signals = []
        EventBus().subscribe(EntrySignal, signals.append)

        # open=99 < vwap=101, close=103 > vwap=101  →  BUY
        EventBus().publish(_candle("TEST", open_p=99.0, close_p=103.0, vwap=101.0))

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].direction, "BUY")
        self.assertEqual(signals[0].symbol, "TEST")

    def test_vwap_cross_sell_generates_entry_signal(self):
        """open > vwap and close < vwap → SELL EntrySignal."""
        signals = []
        EventBus().subscribe(EntrySignal, signals.append)

        # open=103 > vwap=101, close=99 < vwap=101  →  SELL
        EventBus().publish(_candle("TEST", open_p=103.0, close_p=99.0, vwap=101.0))

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].direction, "SELL")

    def test_no_cross_no_signal(self):
        """Candle that stays on one side of VWAP produces no signal."""
        signals = []
        EventBus().subscribe(EntrySignal, signals.append)

        # open=99 < vwap=101, close=100 < vwap=101  →  no cross
        EventBus().publish(_candle("TEST", open_p=99.0, close_p=100.0, vwap=101.0))
        self.assertEqual(len(signals), 0)

    def test_duplicate_same_side_suppressed(self):
        """Two consecutive same-side crosses produce only one signal."""
        signals = []
        EventBus().subscribe(EntrySignal, signals.append)

        bus = EventBus()
        bus.publish(_candle("TEST", open_p=99.0, close_p=103.0, vwap=101.0))
        bus.publish(_candle("TEST", open_p=99.0, close_p=104.0, vwap=101.0))
        self.assertEqual(len(signals), 1)

    def test_entry_signal_creates_order(self):
        """EntrySignal published by VwapStrategy results in an order in OrderManager."""
        bus = EventBus()
        bus.publish(_candle("TEST", open_p=99.0, close_p=103.0, vwap=101.0))
        self.assertTrue(self.order_mgr.has_order("TEST"))
        self.assertEqual(self.order_mgr.get_order("TEST").get_side(), "BUY")

    def test_executor_factory_paper(self):
        """ExecutorFactory creates a paper executor without error."""
        executor = ExecutorFactory.create_executor("paper")
        self.assertIsNotNone(executor)
        self.assertTrue(executor.paper_trade)

    def test_executor_factory_unknown_raises(self):
        with self.assertRaises(ValueError):
            ExecutorFactory.create_executor("unknown_broker_xyz")


if __name__ == "__main__":
    unittest.main()
