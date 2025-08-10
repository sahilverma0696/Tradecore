import unittest
import threading
import time
from datetime import datetime
from unittest.mock import Mock, patch

from src.core.event_bus import (
    EventBus, Event, CandleGenerated, 
    EntrySignal, ExitSignal, Publisher, Subscriber, QuoteReceived
)


class TestEvent(Event):
    """Test event for testing purposes."""
    def __init__(self, data: str, timestamp: datetime = None, source: str = "test"):
        self.data = data
        super().__init__(timestamp=timestamp or datetime.now(), source=source)


class TestEventBus(unittest.TestCase):
    
    def setUp(self):
        """Reset EventBus singleton before each test."""
        # Clear the singleton instance
        EventBus._instance = None
        self.event_bus = EventBus()
    
    def tearDown(self):
        """Clean up after each test."""
        self.event_bus.clear_history()
        EventBus._instance = None
    
    def test_singleton_pattern(self):
        """Test that EventBus follows singleton pattern."""
        bus1 = EventBus()
        bus2 = EventBus()
        self.assertIs(bus1, bus2)
    
    def test_subscribe_and_publish(self):
        """Test basic subscribe and publish functionality."""
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        # Subscribe to TestEvent
        self.event_bus.subscribe(TestEvent, handler)
        
        # Publish an event
        test_event = TestEvent("test data")
        self.event_bus.publish(test_event)
        
        # Verify event was received
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].data, "test data")
    
    def test_multiple_subscribers(self):
        """Test multiple subscribers for the same event type."""
        received_events_1 = []
        received_events_2 = []
        
        def handler1(event):
            received_events_1.append(event)
        
        def handler2(event):
            received_events_2.append(event)
        
        # Subscribe both handlers
        self.event_bus.subscribe(TestEvent, handler1)
        self.event_bus.subscribe(TestEvent, handler2)
        
        # Publish an event
        test_event = TestEvent("broadcast test")
        self.event_bus.publish(test_event)
        
        # Both handlers should receive the event
        self.assertEqual(len(received_events_1), 1)
        self.assertEqual(len(received_events_2), 1)
        self.assertEqual(received_events_1[0].data, "broadcast test")
        self.assertEqual(received_events_2[0].data, "broadcast test")
    
    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        # Subscribe and publish
        self.event_bus.subscribe(TestEvent, handler)
        self.event_bus.publish(TestEvent("first"))
        
        # Unsubscribe and publish again
        self.event_bus.unsubscribe(TestEvent, handler)
        self.event_bus.publish(TestEvent("second"))
        
        # Should only receive the first event
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].data, "first")
    
    def test_event_history(self):
        """Test event history functionality."""
        # Publish some events
        event1 = TestEvent("event1")
        event2 = QuoteReceived(
            timestamp=datetime.now(),
            source="test",
            symbol="TEST",
            instrument="123",
            ltp=100.0,
            last_quantity=10,
            volume=1000,
            change=0.5,
            raw_data={}
        )
        
        self.event_bus.publish(event1)
        self.event_bus.publish(event2)
        
        # Get all history
        history = self.event_bus.get_event_history()
        self.assertEqual(len(history), 2)
        
        # Get filtered history
        test_events = self.event_bus.get_event_history(TestEvent)
        self.assertEqual(len(test_events), 1)
        self.assertEqual(test_events[0].data, "event1")
        
        # Get limited history
        limited = self.event_bus.get_event_history(limit=1)
        self.assertEqual(len(limited), 1)
        self.assertIsInstance(limited[0], QuoteReceived)
    
    def test_max_history_limit(self):
        """Test that event history respects max limit."""
        # Set a small max history for testing
        self.event_bus._max_history = 3
        
        # Publish more events than the limit
        for i in range(5):
            self.event_bus.publish(TestEvent(f"event{i}"))
        
        history = self.event_bus.get_event_history()
        self.assertEqual(len(history), 3)
        # Should contain the last 3 events
        self.assertEqual(history[0].data, "event2")
        self.assertEqual(history[1].data, "event3")
        self.assertEqual(history[2].data, "event4")
    
    def test_thread_safety(self):
        """Test thread safety of the event bus."""
        received_events = []
        lock = threading.Lock()
        
        def handler(event):
            with lock:
                received_events.append(event)
        
        self.event_bus.subscribe(TestEvent, handler)
        
        # Create multiple threads publishing events
        threads = []
        for i in range(10):
            thread = threading.Thread(
                target=lambda i=i: self.event_bus.publish(TestEvent(f"thread{i}"))
            )
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All events should be received
        self.assertEqual(len(received_events), 10)
    
    def test_error_handling(self):
        """Test error handling in event handlers."""
        successful_events = []
        
        def failing_handler(event):
            raise Exception("Handler error")
        
        def successful_handler(event):
            successful_events.append(event)
        
        # Subscribe both handlers
        self.event_bus.subscribe(TestEvent, failing_handler)
        self.event_bus.subscribe(TestEvent, successful_handler)
        
        # Mock the logger directly on the event bus instance
        with patch.object(self.event_bus, '_logger') as mock_logger:
            self.event_bus.publish(TestEvent("error test"))
            
            # Successful handler should still work
            self.assertEqual(len(successful_events), 1)
            # Error should be logged
            mock_logger.error.assert_called()
    
    def test_subscriber_count(self):
        """Test getting subscriber count."""
        def handler1(event): pass
        def handler2(event): pass
        
        # Initially no subscribers
        self.assertEqual(self.event_bus.get_subscriber_count(TestEvent), 0)
        
        # Add subscribers
        self.event_bus.subscribe(TestEvent, handler1)
        self.assertEqual(self.event_bus.get_subscriber_count(TestEvent), 1)
        
        self.event_bus.subscribe(TestEvent, handler2)
        self.assertEqual(self.event_bus.get_subscriber_count(TestEvent), 2)
        
        # Remove subscriber
        self.event_bus.unsubscribe(TestEvent, handler1)
        self.assertEqual(self.event_bus.get_subscriber_count(TestEvent), 1)
    
    def test_list_event_types(self):
        """Test listing event types that have subscribers."""
        def handler(event): pass
        
        # Initially no event types
        self.assertEqual(self.event_bus.list_event_types(), [])
        
        # Add subscribers
        self.event_bus.subscribe(TestEvent, handler)
        self.event_bus.subscribe(QuoteReceived, handler)
        
        event_types = self.event_bus.list_event_types()
        self.assertIn('TestEvent', event_types)
        self.assertIn('QuoteReceived', event_types)
        self.assertEqual(len(event_types), 2)


class TestPublisherMixin(unittest.TestCase):
    
    def setUp(self):
        EventBus._instance = None
    
    def tearDown(self):
        EventBus._instance = None
    
    def test_publisher_mixin(self):
        """Test Publisher mixin functionality."""
        
        class TestPublisher(Publisher):
            def __init__(self):
                super().__init__()
            
            def send_test_event(self, data):
                event = TestEvent(data)
                self.publish_event(event)
        
        received_events = []
        
        def handler(event):
            received_events.append(event)
        
        # Create publisher and subscribe to events
        publisher = TestPublisher()
        event_bus = EventBus()
        event_bus.subscribe(TestEvent, handler)
        
        # Send event through publisher
        publisher.send_test_event("publisher test")
        
        # Verify event was received
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].data, "publisher test")
        self.assertEqual(received_events[0].source, "TestPublisher")


class TestSubscriberMixin(unittest.TestCase):
    
    def setUp(self):
        EventBus._instance = None
    
    def tearDown(self):
        EventBus._instance = None
    
    def test_subscriber_mixin(self):
        """Test Subscriber mixin functionality."""
        
        class TestSubscriber(Subscriber):
            def __init__(self):
                super().__init__()
                self.received_events = []
                self.subscribe_to_event(TestEvent, self.handle_test_event)
            
            def handle_test_event(self, event):
                self.received_events.append(event)
        
        # Create subscriber and publish event
        subscriber = TestSubscriber()
        event_bus = EventBus()
        
        test_event = TestEvent("subscriber test")
        event_bus.publish(test_event)
        
        # Verify event was received
        self.assertEqual(len(subscriber.received_events), 1)
        self.assertEqual(subscriber.received_events[0].data, "subscriber test")
    
    def test_subscriber_unsubscribe_all(self):
        """Test unsubscribing from all events."""
        
        class TestSubscriber(Subscriber):
            def __init__(self):
                super().__init__()
                self.received_events = []
                self.subscribe_to_event(TestEvent, self.handle_test_event)
                self.subscribe_to_event(QuoteReceived, self.handle_quote_event)
            
            def handle_test_event(self, event):
                self.received_events.append(event)
            
            def handle_quote_event(self, event):
                self.received_events.append(event)
        
        subscriber = TestSubscriber()
        event_bus = EventBus()
        
        # Publish events before unsubscribe
        event_bus.publish(TestEvent("before unsubscribe"))
        
        # Unsubscribe from all
        subscriber.unsubscribe_all()
        
        # Publish events after unsubscribe
        event_bus.publish(TestEvent("after unsubscribe"))
        event_bus.publish(QuoteReceived(
            timestamp=datetime.now(),
            source="test",
            symbol="TEST",
            instrument="123",
            ltp=100.0,
            last_quantity=10,
            volume=1000,
            change=0.5,
            raw_data={}
        ))
        
        # Should only receive the first event
        self.assertEqual(len(subscriber.received_events), 1)
        self.assertEqual(subscriber.received_events[0].data, "before unsubscribe")


class TestTradingEvents(unittest.TestCase):
    """Test trading-specific events."""
    
    def test_quote_received_creation(self):
        """Test QuoteReceived event creation."""
        quote_event = QuoteReceived(
            timestamp=datetime.now(),
            source="ZerodhaStreamer",
            symbol="NIFTY",
            instrument="256265",
            ltp=18500.50,
            last_quantity=25,
            volume=1000000,
            change=0.75,
            raw_data={"source": "kite", "exchange": "NSE"}
        )
        
        self.assertEqual(quote_event.symbol, "NIFTY")
        self.assertEqual(quote_event.ltp, 18500.50)
        self.assertEqual(quote_event.last_quantity, 25)
        self.assertEqual(quote_event.raw_data["exchange"], "NSE")
    
    def test_candle_generated_creation(self):
        """Test CandleGenerated event creation."""
        candle_data = {
            'timestamp': datetime.now(),
            'open': 18500.0,
            'high': 18520.0,
            'low': 18495.0,
            'close': 18510.0,
            'volume': 1000000,
            'vwap': 18508.5
        }
        
        candle_event = CandleGenerated(
            timestamp=datetime.now(),
            source="CandleMaker",
            symbol="NIFTY",
            candle_data=candle_data,
            timeframe="5m"
        )
        
        self.assertEqual(candle_event.symbol, "NIFTY")
        self.assertEqual(candle_event.timeframe, "5m")
        self.assertEqual(candle_event.candle_data['vwap'], 18508.5)


class TestEventIntegration(unittest.TestCase):
    """Integration tests for event flow in trading system."""
    
    def setUp(self):
        EventBus._instance = None
        self.event_bus = EventBus()
    
    def tearDown(self):
        EventBus._instance = None
    
    def test_trading_workflow(self):
        """Test complete trading workflow through events."""
        workflow_events = []
        
        def track_events(event):
            workflow_events.append(event.__class__.__name__)
        
        # Subscribe to all event types
        self.event_bus.subscribe(QuoteReceived, track_events)
        self.event_bus.subscribe(CandleGenerated, track_events)
        self.event_bus.subscribe(EntrySignal, track_events)
        self.event_bus.subscribe(ExitSignal, track_events)
        
        # Simulate trading workflow
        # 1. Quote received
        quote = QuoteReceived(
            timestamp=datetime.now(),
            source="Streamer",
            symbol="TEST",
            instrument="123",
            ltp=100.0,
            last_quantity=10,
            volume=1000,
            change=0.5,
            raw_data={}
        )
        self.event_bus.publish(quote)
        
        # 2. Candle generated
        candle = CandleGenerated(
            timestamp=datetime.now(),
            source="CandleMaker",
            symbol="TEST",
            candle_data={"close": 100.5, "vwap": 100.2}
        )
        self.event_bus.publish(candle)
        
        # 3. Entry signal generated
        entry = EntrySignal(
            timestamp=datetime.now(),
            source="Strategy",
            symbol="TEST",
            side="BUY",
            entry_price=100.5,
            entry_vwap=100.2,
            quantity=75,
            exit_steps=[],
            strategy_name="TestStrategy",
            candle_data={}
        )
        self.event_bus.publish(entry)
        
        # 4. Exit signal generated
        exit_signal = ExitSignal(
            timestamp=datetime.now(),
            source="ExitManager",
            symbol="TEST",
            exit_price=101.0,
            exit_reason="PROFIT",
            quantity=75
        )
        self.event_bus.publish(exit_signal)
        
        # Verify workflow
        expected_flow = [
            "QuoteReceived",
            "CandleGenerated", 
            "EntrySignal",
            "ExitSignal"
        ]
        self.assertEqual(workflow_events, expected_flow)


if __name__ == "__main__":
    unittest.main()
    expected_flow = [
        "QuoteReceived",
        "CandleGenerated", 
        "EntrySignal",
        "ExitSignal"
    ]
    self.assertEqual(workflow_events, expected_flow)


if __name__ == "__main__":
    unittest.main()
        