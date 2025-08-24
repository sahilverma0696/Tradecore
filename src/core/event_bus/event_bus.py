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
        self._logger.info("EventBus initialized and ready for component registration")
        
        # IPC support for CLI communication
        self._ipc_enabled = True
        self._ipc_file = "data/live_events.json"
        self._quote_file = "data/live_quotes.json"
        os.makedirs("data", exist_ok=True)
    
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
            
            self._logger.debug(f"📢 Publishing {event.__class__.__name__} to {len(subscribers)} subscribers {event}")
            
            # Notify all subscribers
            for callback in subscribers:
                try:
                    callback(event)
                except Exception as e:
                    subscriber_name = getattr(callback, '__name__', 'unknown')
                    self._logger.error(f"❌ Error in subscriber {subscriber_name} for {event.__class__.__name__}: {e}")
                    self._logger.debug(traceback.format_exc())
            
            # Write to IPC files for CLI access
            if self._ipc_enabled:
                self._write_event_to_ipc(event)
    
    def _write_event_to_ipc(self, event: Event):
        """Write event to IPC file for CLI consumption."""
        try:
            event_type = event.__class__.__name__
            event_data = {
                'timestamp': datetime.now().isoformat(),
                'type': event_type,
                'data': self._serialize_event(event)
            }
            
            # Write to general events file
            try:
                with open(self._ipc_file, 'w') as f:
                    json.dump(event_data, f, indent=2)
            except Exception as e:
                self._logger.debug(f"Could not write to IPC file: {e}")
            
            # Write QuoteEvents to dedicated quotes file for real-time display
            if event_type == 'QuoteEvent':
                try:
                    quote_data = {
                        'timestamp': event.timestamp.isoformat() if hasattr(event.timestamp, 'isoformat') else str(event.timestamp),
                        'symbol': event.instrument,
                        'ltp': event.ltp,
                        'ltq': event.ltq,
                        'source': event.source,
                        'updated_at': datetime.now().isoformat()
                    }
                    
                    # Read existing quotes
                    quotes = {}
                    if os.path.exists(self._quote_file):
                        try:
                            with open(self._quote_file, 'r') as f:
                                quotes = json.load(f)
                        except:
                            quotes = {}
                    
                    # Update with new quote
                    quotes[event.instrument] = quote_data
                    
                    # Write back to file
                    with open(self._quote_file, 'w') as f:
                        json.dump(quotes, f, indent=2)
                        
                except Exception as e:
                    self._logger.debug(f"Could not write quote to IPC file: {e}")
                    
        except Exception as e:
            self._logger.debug(f"IPC write error: {e}")

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
