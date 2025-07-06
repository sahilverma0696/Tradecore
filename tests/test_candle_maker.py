import unittest
from datetime import datetime
from src.core.candle_maker import CandleMaker

class TestCandleMaker(unittest.TestCase):
    def test_handle_quote_and_finalize(self):
        cm = CandleMaker(csv_file=":memory:")
        called = []
        cm.register_handler(lambda name, candle: called.append((name, candle)))
        quote = {
            "ts": datetime(2023, 1, 1, 9, 15),
            "inst": 1,
            "name": "TEST",
            "ltp": 100,
            "last_quantity": 10,
            "volume": 10,
            "change": 0.0
        }
        cm.handle_quote(quote)
        # Force finalize
        cm._finalize(1, cm._current[1])
        self.assertTrue(called)
        self.assertEqual(called[0][0], "TEST")

if __name__ == "__main__":
    unittest.main()
