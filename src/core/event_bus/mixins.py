from typing import Type, Callable
from .event_bus import EventBus
from .events import Event


class Publisher:
    """Mixin class for components that publish events."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_bus = EventBus()
    
    def publish_event(self, event: Event):
        """Publish an event to the event bus."""
        event.source = getattr(self, '__class__').__name__
        self._event_bus.publish(event)


class Subscriber:
    """Mixin class for components that subscribe to events."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._event_bus = EventBus()
        self._subscriptions = []
    
    def subscribe_to_event(self, event_type: Type[Event], callback: Callable[[Event], None]):
        """Subscribe to an event type."""
        self._event_bus.subscribe(event_type, callback, self.__class__.__name__)
        self._subscriptions.append((event_type, callback))
    
    def unsubscribe_from_event(self, event_type: Type[Event], callback: Callable[[Event], None]):
        """Unsubscribe from an event type."""
        self._event_bus.unsubscribe(event_type, callback)
        if (event_type, callback) in self._subscriptions:
            self._subscriptions.remove((event_type, callback))
    
    def unsubscribe_all(self):
        """Unsubscribe from all events."""
        for event_type, callback in self._subscriptions:
            self._event_bus.unsubscribe(event_type, callback)
        self._subscriptions.clear()
