import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from src.strategies.vwap_strategy import VwapStrategy
from src.core.order_manager import OrderManager
from src.core.order_object import OrderObject
from src.core.event_bus import EventBus, EntrySignal, CandleGenerated
from src.core.executors import ExecutorFactory, BaseExecutor

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

    def test_executor_factory(self):
        """Test executor factory functionality."""
        # Test Zerodha executor creation
        zerodha_executor = ExecutorFactory.create_executor(
            'zerodha', 
            paper_trade=True,
            config={'max_retries': 2}
        )
        self.assertIsNotNone(zerodha_executor)
        self.assertTrue(zerodha_executor.paper_trade)
        self.assertEqual(zerodha_executor.max_retries, 2)
        
        # Test Binance executor creation
        binance_executor = ExecutorFactory.create_executor(
            'binance',
            paper_trade=True
        )
        self.assertIsNotNone(binance_executor)
        
        # Test unsupported broker
        with self.assertRaises(ValueError):
            ExecutorFactory.create_executor('unsupported_broker')

    def test_order_execution_with_modern_executor(self):
        """Test order execution with modern executor pattern."""
        # Create executor with paper trading
        executor = ExecutorFactory.create_executor(
            'zerodha',
            client=None,
            paper_trade=True,
            config={'max_retries': 2, 'default_quantity': 50}
        )
        
        # Test order execution
        result = executor.execute_order("TESTSYM", "BUY", datetime.now())
        self.assertTrue(result)
        
        # Check that trade was recorded
        stats = executor.get_execution_stats()
        self.assertEqual(stats['total_orders'], 1)
        self.assertEqual(stats['open_trades'], 1)

    def test_paper_trading_mode(self):
        """Test paper trading mode with different brokers."""
        brokers = ['zerodha', 'binance', 'upstox']
        
        for broker in brokers:
            with self.subTest(broker=broker):
                executor = ExecutorFactory.create_executor(broker, paper_trade=True)
                
                # Paper trade should always succeed
                result = executor.execute_order("TESTSYM", "BUY", datetime.now())
                self.assertTrue(result)
                
                # Check stats
                stats = executor.get_execution_stats()
                self.assertTrue(stats['paper_trade'])
                self.assertEqual(stats['total_orders'], 1)

if __name__ == "__main__":
    unittest.main()
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
