"""Tests for executor layer: factory, paper trading, order lifecycle."""
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.core.event_bus import EventBus
from src.core.event_bus.events import OrderEvent, CandleGenerated
from src.core.executors.executor_factory import ExecutorFactory
from src.core.executors.binance_executor import BinanceExecutor
from src.core.executors.base_executor import BaseExecutor


def _reset_bus():
    EventBus._instance = None


def _make_order_event(instrument="BTCUSDT", side="BUY") -> OrderEvent:
    return OrderEvent(
        timestamp=datetime.now(),
        source="test",
        order_id="ord_001",
        instrument=instrument,
        side=side,
        price=42000.0,
        strategy="VWAP",
        type="ENTRY",
    )


class TestExecutorFactory(unittest.TestCase):

    def setUp(self):
        _reset_bus()

    def tearDown(self):
        _reset_bus()

    def test_available_includes_builtins(self):
        available = ExecutorFactory.available()
        self.assertIn("paper", available)
        self.assertIn("binance", available)

    def test_is_available(self):
        self.assertTrue(ExecutorFactory.is_available("paper"))
        self.assertTrue(ExecutorFactory.is_available("binance"))
        self.assertFalse(ExecutorFactory.is_available("nonexistent"))

    def test_create_paper_executor(self):
        ex = ExecutorFactory.create_executor("paper", config={})
        self.assertIsInstance(ex, BaseExecutor)
        self.assertTrue(ex.paper_trade)

    def test_create_paper_is_case_insensitive(self):
        ex = ExecutorFactory.create_executor("PAPER", config={})
        self.assertTrue(ex.paper_trade)

    def test_unknown_type_raises(self):
        with self.assertRaises((ValueError, Exception)):
            ExecutorFactory.create_executor("fakexyz", config={})

    def test_register_custom_executor(self):
        class DummyExecutor(BinanceExecutor):
            pass
        ExecutorFactory.register("dummy_exec", DummyExecutor)
        self.assertIn("dummy_exec", ExecutorFactory.available())


class TestPaperTrading(unittest.TestCase):

    def setUp(self):
        _reset_bus()
        self.ex = BinanceExecutor(client=None, paper_trade=True, config={})

    def tearDown(self):
        _reset_bus()

    @patch.object(BinanceExecutor, '_get_quantity', return_value=1)
    def test_paper_execute_records_trade(self, _):
        ok = self.ex.execute_order("BTCUSDT", "BUY")
        self.assertTrue(ok)
        self.assertEqual(len(self.ex.open_trades), 1)
        self.assertEqual(self.ex.total_executed_orders, 1)

    @patch.object(BinanceExecutor, '_get_quantity', return_value=1)
    def test_paper_trade_has_paper_prefix(self, _):
        self.ex.execute_order("BTCUSDT", "BUY")
        order_id = list(self.ex.open_trades.keys())[0]
        self.assertTrue(order_id.startswith("PAPER_"))

    @patch.object(BinanceExecutor, '_get_quantity', return_value=1)
    def test_paper_trade_side_stored_correctly(self, _):
        self.ex.execute_order("BTCUSDT", "SELL")
        trade = list(self.ex.open_trades.values())[0]
        self.assertEqual(trade["side"], "SELL")
        self.assertEqual(trade["status"], "FILLED")

    @patch.object(BinanceExecutor, '_get_quantity', return_value=1)
    def test_cancel_paper_order(self, _):
        self.ex.execute_order("BTCUSDT", "BUY")
        order_id = list(self.ex.open_trades.keys())[0]
        ok = self.ex.cancel_order(order_id)
        self.assertTrue(ok)
        self.assertEqual(self.ex.open_trades[order_id]["status"], "CANCELLED")

    def test_cancel_nonexistent_order(self):
        ok = self.ex.cancel_order("nonexistent_id")
        self.assertFalse(ok)

    @patch.object(BinanceExecutor, '_get_quantity', return_value=1)
    def test_multiple_orders_tracked(self, _):
        self.ex.execute_order("BTCUSDT", "BUY")
        self.ex.execute_order("ETHUSDT", "SELL")
        self.assertEqual(self.ex.total_executed_orders, 2)
        self.assertEqual(len(self.ex.open_trades), 2)

    @patch.object(BinanceExecutor, '_get_quantity', return_value=1)
    def test_get_execution_stats(self, _):
        self.ex.execute_order("BTCUSDT", "BUY")
        stats = self.ex.get_execution_stats()
        self.assertEqual(stats["total_orders"], 1)
        self.assertEqual(stats["open_trades"], 1)
        self.assertTrue(stats["paper_trade"])


class TestOrderEventDispatch(unittest.TestCase):

    def setUp(self):
        _reset_bus()

    def tearDown(self):
        _reset_bus()

    @patch.object(BinanceExecutor, '_get_quantity', return_value=1)
    def test_order_event_triggers_execute(self, _):
        ex = BinanceExecutor(client=None, paper_trade=True, config={})
        event = _make_order_event("BTCUSDT", "BUY")
        EventBus().publish(event)
        self.assertEqual(ex.total_executed_orders, 1)

    @patch.object(BinanceExecutor, '_get_quantity', return_value=1)
    def test_buy_and_sell_events(self, _):
        ex = BinanceExecutor(client=None, paper_trade=True, config={})
        EventBus().publish(_make_order_event("BTCUSDT", "BUY"))
        EventBus().publish(_make_order_event("BTCUSDT", "SELL"))
        self.assertEqual(ex.total_executed_orders, 2)


class TestDirectionNormalization(unittest.TestCase):

    def setUp(self):
        _reset_bus()
        self.ex = BinanceExecutor(client=None, paper_trade=True, config={})

    def tearDown(self):
        _reset_bus()

    def test_buy_variants(self):
        for v in ("BUY", "buy", "B", "b"):
            self.assertEqual(self.ex._normalize_direction(v), "BUY")

    def test_sell_variants(self):
        for v in ("SELL", "sell", "S", "s"):
            self.assertEqual(self.ex._normalize_direction(v), "SELL")

    def test_invalid_direction_raises(self):
        with self.assertRaises(ValueError):
            self.ex._normalize_direction("LONG")


if __name__ == "__main__":
    unittest.main()
