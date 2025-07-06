import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from src.strategies.vwap_strategy import VwapStrategy
from src.core.order_manager import OrderManager
from src.core.order_object import OrderObject

class TestVWAPFlow(unittest.TestCase):
    def setUp(self):
        # Minimal config for testing
        self.config = {
            "exit_steps": [(0.02, 0.5), (0.04, 0.5)],
            "market_close_time": "15:30",
            "exit_max_pct": 0.01,
            "default_quantity": 10,
            "name_symbol": {"TEST": "TESTSYM"},
        }
        self.strategy = VwapStrategy(config=self.config)
        self.order_mgr = OrderManager()
        self.symbol = "TEST"
        self.candle = {
            "timestamp": datetime.now(),
            "open": 100,
            "high": 105,
            "low": 99,
            "close": 106,
            "volume": 1000,
            "name": self.symbol,
        }

    def test_entry_and_exit_flow(self):
        # Simulate a BUY entry
        self.strategy.on_candle(self.symbol, self.candle)
        self.assertIn(self.symbol, self.strategy.positions)
        pos = self.strategy.positions[self.symbol]
        self.assertEqual(pos['side'], 'BUY')
        self.assertEqual(pos['entry_price'], self.candle['close'])

        # Simulate order creation in order manager
        self.order_mgr.create_order(
            timestamp=pos['entry_time'],
            name=self.symbol,
            instrument="TESTSYM",
            step=[s[0] for s in pos['steps']],
            trail=[self.config['exit_max_pct']] * len(pos['steps']),
            side=pos['side'],
            candle=self.candle,
            quantity=pos['quantity']
        )
        self.assertTrue(self.order_mgr.has_order(self.symbol))

        # Simulate a quote that triggers a step exit
        step_exit_price = pos['entry_price'] * (1 + 0.02)
        self.strategy._manage_position(self.symbol, step_exit_price, pos['entry_vwap'], self.candle['timestamp'].time(), datetime.now())
        # Should have reduced remaining_qty or removed position if all exited

    def test_trailing_exit(self):
        # Simulate entry
        self.strategy.on_candle(self.symbol, self.candle)
        pos = self.strategy.positions[self.symbol]
        # Simulate price moves up, then retraces
        pos['max_profit_price'] = 120
        retrace_price = 120 * (1 - self.config['exit_max_pct'])
        self.strategy._manage_position(self.symbol, retrace_price, pos['entry_vwap'], self.candle['timestamp'].time(), datetime.now())
        # Should trigger trailing exit

    def test_risk_exit(self):
        # Simulate entry
        self.strategy.on_candle(self.symbol, self.candle)
        pos = self.strategy.positions[self.symbol]
        # Simulate quote below vwap for BUY
        vwap = pos['entry_vwap']
        self.strategy._check_risk_exit(self.symbol, vwap - 10, vwap, datetime.now())
        # Should trigger risk exit

    def test_order_object(self):
        order = OrderObject(
            name="TEST",
            instrument="TESTSYM",
            step=[0.02, 0.04],
            trail=[0.01, 0.01],
            side="BUY",
            candle=self.candle
        )
        order.set_ltp(110)
        self.assertGreater(order.get_ltp(), order.get_entry_price())
        order.update_step()
        self.assertTrue(order.get_current_step() >= 0.02)

if __name__ == "__main__":
    unittest.main()
