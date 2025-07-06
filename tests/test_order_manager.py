import unittest
from datetime import datetime
from src.core.order_manager import OrderManager

class TestOrderManager(unittest.TestCase):
    def test_create_and_remove_order(self):
        om = OrderManager()
        order = om.create_order(
            timestamp=datetime.now(),
            name="TEST",
            instrument="TESTSYM",
            step=[0.02, 0.04],
            trail=[0.01, 0.01],
            side="BUY",
            candle={"close": 100},
            quantity=10
        )
        self.assertTrue(om.has_order("TEST"))
        om.update_ltp("TEST", 105)
        om.remove_order("TEST", datetime.now(), "TEST_EXIT", 105)
        self.assertFalse(om.has_order("TEST"))

if __name__ == "__main__":
    unittest.main()
