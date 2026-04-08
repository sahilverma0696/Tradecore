"""Tests for streamer layer: factory, normalization, lifecycle."""
import threading
import time
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.core.event_bus import EventBus
from src.core.event_bus.events import QuoteEvent
from src.core.streamer.binance_streamer import BinanceStreamer
from src.core.streamer.offline_streamer import OfflineStreamer
from src.core.streamer.streamer_factory import StreamerFactory
from src.core.thread_manager import ThreadManager


def _reset_bus():
    EventBus._instance = None


class TestStreamerFactory(unittest.TestCase):

    def setUp(self):
        _reset_bus()

    def tearDown(self):
        _reset_bus()

    def test_available_includes_builtins(self):
        available = StreamerFactory.available()
        self.assertIn("offline", available)
        self.assertIn("binance", available)

    def test_is_streamer_available(self):
        self.assertTrue(StreamerFactory.is_streamer_available("offline"))
        self.assertFalse(StreamerFactory.is_streamer_available("nonexistent_broker"))

    def test_create_offline_streamer(self):
        s = StreamerFactory.create_streamer(
            "offline", symbols=["TEST"],
            config={"base_price": 100.0, "tick_interval": 0.1}
        )
        self.assertIsInstance(s, OfflineStreamer)
        self.assertEqual(s.symbols, ["TEST"])

    def test_create_binance_streamer(self):
        s = StreamerFactory.create_streamer(
            "binance", symbols=["btcusdt"],
            config={"reconnect_attempts": 3, "reconnect_delay": 1.0}
        )
        self.assertIsInstance(s, BinanceStreamer)
        self.assertEqual(s.reconnect_attempts, 3)

    def test_unknown_type_raises(self):
        with self.assertRaises(ValueError):
            StreamerFactory.create_streamer("fakecoin", symbols=["X"])

    def test_register_custom_streamer(self):
        class DummyStreamer(OfflineStreamer):
            pass
        StreamerFactory.register("dummy", DummyStreamer)
        self.assertIn("dummy", StreamerFactory.available())
        s = StreamerFactory.create_streamer("dummy", symbols=["SYM"])
        self.assertIsInstance(s, DummyStreamer)


class TestBinanceStreamerNormalization(unittest.TestCase):

    def setUp(self):
        _reset_bus()
        self.streamer = BinanceStreamer(symbols=["BTCUSDT"])

    def tearDown(self):
        _reset_bus()

    def test_normalize_valid_trade(self):
        raw = {"s": "BTCUSDT", "p": "42000.50", "q": "0.001", "T": 1700000000000}
        event = self.streamer._normalize_raw_data(raw, "BTCUSDT")
        self.assertIsNotNone(event)
        self.assertIsInstance(event, QuoteEvent)
        self.assertAlmostEqual(event.ltp, 42000.50)
        self.assertAlmostEqual(event.ltq, 0.001)
        self.assertEqual(event.instrument, "BTCUSDT")

    def test_normalize_uses_symbol_from_data(self):
        raw = {"s": "ETHUSDT", "p": "2000.0", "q": "1.0", "T": 1700000000000}
        event = self.streamer._normalize_raw_data(raw, "BTCUSDT")
        self.assertEqual(event.instrument, "ETHUSDT")

    def test_normalize_missing_timestamp_defaults_to_now(self):
        raw = {"s": "BTCUSDT", "p": "100.0", "q": "1.0"}
        before = datetime.now()
        event = self.streamer._normalize_raw_data(raw, "BTCUSDT")
        after = datetime.now()
        self.assertIsNotNone(event)
        self.assertGreaterEqual(event.timestamp, before)
        self.assertLessEqual(event.timestamp, after)

    def test_normalize_bad_data_returns_none(self):
        event = self.streamer._normalize_raw_data({"bad": "data", "p": "not_a_float"}, "X")
        self.assertIsNone(event)

    def test_setup_connection_builds_ws_url(self):
        self.streamer._setup_connection()
        self.assertIsNotNone(self.streamer._ws)
        ws_url = self.streamer._ws.url
        self.assertIn("btcusdt@trade", ws_url)
        self.assertIn("stream.binance.com", ws_url)

    def test_setup_connection_testnet_url(self):
        s = BinanceStreamer(symbols=["btcusdt"], testnet=True)
        s._setup_connection()
        self.assertIn("testnet.binance.vision", s._ws.url)


class TestOfflineStreamer(unittest.TestCase):

    def setUp(self):
        _reset_bus()
        from src.core.thread_manager import ThreadManager
        self._tm = ThreadManager()
        self._tm.initialize_pools()

    def tearDown(self):
        self._tm.shutdown(wait=False)
        ThreadManager._instance = None
        _reset_bus()

    def test_initial_state(self):
        s = OfflineStreamer(symbols=["SYM"], tick_interval=0.1)
        self.assertFalse(s.is_running())

    def test_publishes_quote_events(self):
        received = []
        EventBus().subscribe(QuoteEvent, received.append)

        s = OfflineStreamer(symbols=["SYM"], base_price=500.0, tick_interval=0.05)
        t = threading.Thread(target=s.start, daemon=True)
        t.start()
        time.sleep(0.3)
        s.stop()
        t.join(timeout=2)

        self.assertTrue(len(received) > 0)
        for ev in received:
            self.assertIsInstance(ev, QuoteEvent)
            self.assertEqual(ev.instrument, "SYM")
            self.assertGreater(ev.ltp, 0)

    def test_stop_halts_streaming(self):
        s = OfflineStreamer(symbols=["SYM"], tick_interval=0.05)
        t = threading.Thread(target=s.start, daemon=True)
        t.start()
        time.sleep(0.2)
        s.stop()
        t.join(timeout=2)
        self.assertFalse(s.is_running())

    def test_multiple_symbols(self):
        received = []
        EventBus().subscribe(QuoteEvent, received.append)

        s = OfflineStreamer(symbols=["AAA", "BBB"], tick_interval=0.05)
        t = threading.Thread(target=s.start, daemon=True)
        t.start()
        time.sleep(0.4)
        s.stop()
        t.join(timeout=2)

        symbols_seen = {ev.instrument for ev in received}
        self.assertIn("AAA", symbols_seen)
        self.assertIn("BBB", symbols_seen)


if __name__ == "__main__":
    unittest.main()
