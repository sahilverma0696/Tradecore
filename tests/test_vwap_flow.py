import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from src.strategies.vwap_strategy import VwapStrategy
from src.core.order_manager import OrderManager
from src.core.order_object import OrderObject
from src.core.event_bus import EventBus, EntrySignal, CandleGenerated

class TestVWAPFlow(unittest.TestCase):
    def setUp(self):
        # Reset EventBus singleton
        EventBus._instance = None
        
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
            "vwap": 102  # Add VWAP for entry logic
        }

    def tearDown(self):
        """Clean up after each test."""
        EventBus._instance = None

    def test_entry_and_exit_flow(self):
        """Test complete entry and exit flow using event bus."""
        event_bus = EventBus()
        entry_signals = []
        
        # Subscribe to entry signals
        def handle_entry(event: EntrySignal):
            entry_signals.append(event)
            # Convert to signal format for order manager
            signal_data = {
                'signal': 'ENTER',
                'symbol': event.symbol,
                'side': event.side,
                'entry_price': event.entry_price,
                'entry_time': event.timestamp,
                'name': event.symbol,
                'entry_vwap': event.entry_vwap,
                'quantity': event.quantity,
                'steps': event.exit_steps,
                'candle': event.candle_data
            }
            self.order_mgr.handle_signal(signal_data)
        
        event_bus.subscribe(EntrySignal, handle_entry)
        
        # Simulate VWAP cross: open < vwap, close > vwap (BUY signal)
        candle_with_cross = self.candle.copy()
        candle_with_cross['open'] = 101  # Below VWAP
        candle_with_cross['close'] = 103  # Above VWAP
        candle_with_cross['vwap'] = 102
        
        # Trigger candle event
        candle_event = CandleGenerated(
            timestamp=datetime.now(),
            source="TestCandleMaker",
            symbol=self.symbol,
            candle_data=candle_with_cross
        )
        event_bus.publish(candle_event)
        
        # Verify entry signal was generated
        self.assertEqual(len(entry_signals), 1)
        self.assertEqual(entry_signals[0].side, 'BUY')
        self.assertEqual(entry_signals[0].symbol, self.symbol)
        
        # Verify order was created
        self.assertTrue(self.order_mgr.has_order(self.symbol))
        order = self.order_mgr.get_order(self.symbol)
        self.assertEqual(order.get_side(), 'BUY')

    def test_order_execution_with_mock_client(self):
        """Test order execution with mock client."""
        # Create mock client for testing
        mock_client = MagicMock()
        mock_client.place_order.return_value = {"order_id": "TEST123"}
        mock_client.VARIETY_REGULAR = "regular"
        mock_client.EXCHANGE_NFO = "NFO"
        mock_client.TRANSACTION_TYPE_BUY = "BUY"
        mock_client.TRANSACTION_TYPE_SELL = "SELL"
        mock_client.ORDER_TYPE_MARKET = "MARKET"
        mock_client.PRODUCT_MIS = "MIS"
        
        from src.core.executioner import Execute
        
        # Mock the config file reading
        mock_config = {
            'execution': {
                'delta_sell': 0,
                'delta_buy': 0,
                'max_retries': 2,
                'retry_delay': 1,
                'quantities': {'default': 75}
            }
        }
        
        with patch('builtins.open', unittest.mock.mock_open()), \
             patch('json.load', return_value=mock_config):
            execer = Execute(client=mock_client, paper_trade=False, logger=None)
            
            # Test order execution
            result = execer.execute_order("TESTSYM", "B", datetime.now())
            self.assertTrue(result)
            mock_client.place_order.assert_called_once()

    def test_order_object_functionality(self):
        """Test OrderObject functionality."""
        order = OrderObject(
            name="TEST",
            instrument="TESTSYM",
            step=[0.02, 0.04],
            trail=[0.01, 0.01],
            side="BUY",
            candle=self.candle
        )
        
        # Test initial state
        self.assertEqual(order.get_side(), "BUY")
        self.assertEqual(order.get_entry_price(), self.candle['close'])
        
        # Test LTP update
        order.set_ltp(110)
        self.assertEqual(order.get_ltp(), 110)
        self.assertGreater(order.get_ltp(), order.get_entry_price())
        
        # Test step progression
        initial_step = order.get_current_step()
        order.update_step()
        # Step should progress if price moved enough
        self.assertGreaterEqual(order.get_current_step(), initial_step)

    def test_paper_trading_mode(self):
        """Test paper trading mode."""
        from src.core.executioner import Execute
        
        mock_config = {
            'execution': {
                'delta_sell': 0,
                'delta_buy': 0,
                'max_retries': 2,
                'retry_delay': 1,
                'quantities': {'default': 75}
            }
        }
        
        with patch('builtins.open', unittest.mock.mock_open()), \
             patch('json.load', return_value=mock_config):
            execer = Execute(client=None, paper_trade=True, logger=None)
            
            # Paper trade should always succeed
            result = execer.execute_order("TESTSYM", "B", datetime.now())
            self.assertTrue(result)

if __name__ == "__main__":
    unittest.main()
