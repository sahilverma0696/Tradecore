import unittest
from datetime import datetime
from src.core.order_manager import OrderManager
from src.core.event_bus import EventBus
from src.core.event_bus.events import EntrySignal, CandleGenerated


def _candle(symbol="TEST", open_p=100.0, close_p=103.0, vwap=101.0):
    return CandleGenerated(
        timestamp=datetime.now(),
        source="TestCandleMaker",
        symbol=symbol,
        timeframe="3",
        open=open_p,
        high=max(open_p, close_p),
        low=min(open_p, close_p),
        close=close_p,
        volume=1000,
        vwap=vwap,
    )


def _entry_signal(symbol="TEST", side="BUY", price=103.0, candle=None):
    return EntrySignal(
        timestamp=datetime.now(),
        source="TestStrategy",
        symbol=symbol,
        direction=side,
        price=price,
        strategy="TestStrategy",
        candle=candle or _candle(symbol),
    )


class TestOrderManager(unittest.TestCase):
    def setUp(self):
        EventBus._instance = None

    def tearDown(self):
        EventBus._instance = None

    def test_order_created_on_entry_signal(self):
        """OrderManager creates a position when it receives an EntrySignal."""
        om = OrderManager()
        bus = EventBus()
        bus.publish(_entry_signal("TEST", "BUY"))
        self.assertTrue(om.has_order("TEST"))

    def test_duplicate_signal_same_side_ignored(self):
        """Second signal for the same symbol/side does not create a duplicate order."""
        om = OrderManager()
        bus = EventBus()
        bus.publish(_entry_signal("TEST", "BUY"))
        bus.publish(_entry_signal("TEST", "BUY"))
        # Still just one order, not two
        self.assertEqual(len(list(om.all_orders())), 1)

    def test_direction_switch_replaces_order(self):
        """Opposite-side signal closes old order and opens a new one in the new direction."""
        om = OrderManager()
        bus = EventBus()
        bus.publish(_entry_signal("TEST", "BUY"))
        self.assertEqual(om.get_order("TEST").get_side(), "BUY")

        bus.publish(_entry_signal("TEST", "SELL"))
        order = om.get_order("TEST")
        self.assertIsNotNone(order)
        self.assertEqual(order.get_side(), "SELL")

    def test_has_order_false_for_unknown_symbol(self):
        OrderManager()
        om = OrderManager()
        self.assertFalse(om.has_order("DOESNOTEXIST"))


if __name__ == "__main__":
    unittest.main()
