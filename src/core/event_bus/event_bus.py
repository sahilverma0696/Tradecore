import threading
from typing import Dict, List, Callable, Type, Any
from collections import defaultdict
import traceback
from src.logger_factory import get_logger
from .events import Event
import json
import os
from datetime import datetime


class EventBus:
    """Thread-safe event bus for pub-sub communication in trading system."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._subscribers: Dict[Type[Event], List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._logger = get_logger("EventBus", console_output=True)
        self._event_history: List[Event] = []
        self._max_history = 1000
        self._initialized = True
        
        # IPC support for CLI communication
        self._ipc_enabled = True
        self._ipc_file = "data/live_events.json"
        self._quote_file = "data/live_quotes.json"
        self._candle_file = "data/live_candles.json"
        os.makedirs("data", exist_ok=True)
        
        # ThreadManager for async IPC operations (lazy initialization)
        self._thread_manager = None
        
        self._logger.info("EventBus initialized and ready for component registration")
    
    def _get_thread_manager(self):
        """Lazy initialization of ThreadManager to avoid circular imports."""
        if self._thread_manager is None:
            try:
                from src.core.thread_manager import ThreadManager, ThreadPoolType
                self._thread_manager = ThreadManager()
                self._ThreadPoolType = ThreadPoolType
            except ImportError:
                self._logger.warning("ThreadManager not available, IPC writes will be synchronous")
                self._thread_manager = False
        return self._thread_manager

    def subscribe(self, event_type: Type[Event], callback: Callable[[Event], None], 
                  subscriber_name: str = None):
        """Subscribe to events of a specific type."""
        with self._lock:
            self._subscribers[event_type].append(callback)
            subscriber_name = subscriber_name or getattr(callback, '__name__', 'unknown')
            self._logger.info(f"📝 {subscriber_name} subscribed to {event_type.__name__}")
    
    def unsubscribe(self, event_type: Type[Event], callback: Callable[[Event], None]):
        """Unsubscribe from events of a specific type."""
        with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                self._logger.debug(f"Unsubscribed from {event_type.__name__}")
    
    def publish(self, event: Event):
        """Publish an event to all subscribers."""
        with self._lock:
            # Store event in history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)
            
            # Get subscribers for this event type and its parent types
            subscribers = []
            for event_class in event.__class__.__mro__:
                if event_class in self._subscribers:
                    subscribers.extend(self._subscribers[event_class])
            
            # self._logger.debug(f"📢 Publishing {event.__class__.__name__} to {len(subscribers)} subscribers {event}")
            
            # Notify all subscribers
            for callback in subscribers:
                try:
                    callback(event)
                except Exception as e:
                    subscriber_name = getattr(callback, '__name__', 'unknown')
                    self._logger.error(f"❌ Error in subscriber {subscriber_name} for {event.__class__.__name__}: {e}")
                    self._logger.debug(traceback.format_exc())
            
            # Write to IPC files asynchronously via ThreadManager
            if self._ipc_enabled:
                self._schedule_ipc_write(event)
    
    def _schedule_ipc_write(self, event: Event):
        """Schedule IPC write operation asynchronously to prevent EventBus blocking."""
        thread_manager = self._get_thread_manager()
        
        if thread_manager and thread_manager is not False:
            # Submit IPC write task to SYSTEM thread pool (I/O operations)
            try:
                thread_manager.submit_task(
                    self._ThreadPoolType.SYSTEM,
                    self._write_event_to_ipc,
                    event
                )
            except Exception as e:
                self._logger.debug(f"Could not schedule IPC write task: {e}")
                # Fallback to synchronous write
                self._write_event_to_ipc(event)
        else:
            # Fallback to synchronous write if ThreadManager not available
            self._write_event_to_ipc(event)

    def _write_event_to_ipc(self, event: Event):
        """Write event to IPC file for CLI consumption (runs in SYSTEM thread pool)."""
        try:
            event_type = event.__class__.__name__
            
            # Handle different event types with specific IPC files
            if event_type == 'QuoteEvent':
                self._write_quote_ipc(event)
            elif event_type == 'CandleGenerated':
                self._write_candle_ipc(event)
            
            # Always write to general events file
            self._write_general_event_ipc(event)
                    
        except Exception as e:
            self._logger.debug(f"IPC write error: {e}")

    def _write_quote_ipc(self, event: Event):
        """Write QuoteEvent to dedicated quotes file."""
        try:
            quote_data = {
                event.instrument: {
                    'symbol': event.instrument,
                    'ltp': float(event.ltp),
                    'ltq': float(event.ltq),
                    'timestamp': event.timestamp.isoformat() if hasattr(event.timestamp, 'isoformat') else str(event.timestamp),
                    'source': event.source
                }
            }
            
            # Read existing quotes
            existing_quotes = {}
            if os.path.exists(self._quote_file):
                try:
                    with open(self._quote_file, 'r') as f:
                        existing_quotes = json.load(f)
                except:
                    existing_quotes = {}
            
            # Update with new quote
            existing_quotes.update(quote_data)
            
            # Keep only last 10 symbols to prevent file from growing too large
            if len(existing_quotes) > 10:
                sorted_items = sorted(existing_quotes.items(), 
                                    key=lambda x: x[1].get('timestamp', ''), 
                                    reverse=True)
                existing_quotes = dict(sorted_items[:10])
            
            # Write updated quotes
            with open(self._quote_file, 'w') as f:
                json.dump(existing_quotes, f, indent=2)
                        
        except Exception as e:
            self._logger.debug(f"Could not write quote to IPC file: {e}")

    def _write_candle_ipc(self, event: Event):
        """Write CandleGenerated event to dedicated candles file."""
        try:
            candle_data = {
                event.symbol: {
                    'symbol': event.symbol,
                    'timeframe': event.timeframe,
                    'timestamp': event.timestamp.isoformat() if hasattr(event.timestamp, 'isoformat') else str(event.timestamp),
                    'open': float(event.open),
                    'high': float(event.high),
                    'low': float(event.low),
                    'close': float(event.close),
                    'volume': float(event.volume),
                    'vwap': float(event.vwap),
                    'is_complete': event.is_complete,
                    'source': event.source
                }
            }
            
            # Read existing candles
            existing_candles = {}
            if os.path.exists(self._candle_file):
                try:
                    with open(self._candle_file, 'r') as f:
                        existing_candles = json.load(f)
                except:
                    existing_candles = {}
            
            # Update with new candle
            existing_candles.update(candle_data)
            
            # Keep only last 5 symbols to prevent file from growing too large
            if len(existing_candles) > 5:
                sorted_items = sorted(existing_candles.items(), 
                                    key=lambda x: x[1].get('timestamp', ''), 
                                    reverse=True)
                existing_candles = dict(sorted_items[:5])
            
            # Write updated candles
            with open(self._candle_file, 'w') as f:
                json.dump(existing_candles, f, indent=2)
                        
        except Exception as e:
            self._logger.debug(f"Could not write candle to IPC file: {e}")

    def _write_general_event_ipc(self, event: Event):
        """Write general event to main IPC file."""
        try:
            event_data = {
                'timestamp': datetime.now().isoformat(),
                'type': event.__class__.__name__,
                'data': self._serialize_event(event)
            }
            
            # Write to general events file (always overwrite with latest)
            with open(self._ipc_file, 'w') as f:
                json.dump(event_data, f, indent=2)
                
        except Exception as e:
            self._logger.debug(f"Could not write general event to IPC file: {e}")

    def _serialize_event(self, event: Event):
        """Serialize event for IPC."""
        try:
            data = {}
            for attr in dir(event):
                if not attr.startswith('_') and not callable(getattr(event, attr)):
                    value = getattr(event, attr)
                    if hasattr(value, 'isoformat'):  # datetime
                        data[attr] = value.isoformat()
                    elif isinstance(value, (str, int, float, bool, list, dict)):
                        data[attr] = value
                    else:
                        data[attr] = str(value)
            return data
        except Exception as e:
            self._logger.debug(f"Serialization error: {e}")
            return {'error': 'serialization_failed'}

    def get_event_history(self, event_type: Type[Event] = None, limit: int = None) -> List[Event]:
        """Get event history, optionally filtered by type."""
        with self._lock:
            events = self._event_history
            if event_type:
                events = [e for e in events if isinstance(e, event_type)]
            if limit:
                events = events[-limit:]
            return events.copy()
    
    def clear_history(self):
        """Clear event history."""
        with self._lock:
            self._event_history.clear()
            self._logger.debug("Event history cleared")
    
    def get_subscriber_count(self, event_type: Type[Event]) -> int:
        """Get number of subscribers for an event type."""
        with self._lock:
            return len(self._subscribers.get(event_type, []))
    
    def list_event_types(self) -> List[str]:
        """Get list of all event types that have subscribers."""
        with self._lock:
            return [event_type.__name__ for event_type in self._subscribers.keys()]
