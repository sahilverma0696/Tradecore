from .base_streamer import BaseStreamer
from src.core.event_bus.events import QuoteEvent
from .streamer_factory import StreamerFactory

# Import specific streamers if available
try:
    from .zerodha_streamer import ZerodhaStreamer
except ImportError:
    ZerodhaStreamer = None

try:
    from .offline_streamer import OfflineStreamer
except ImportError:
    OfflineStreamer = None

__all__ = [
    'BaseStreamer', 
    'QuoteNormalizer', 
    'QuoteEvent', 
    'StreamerFactory'
]

# Add available streamers to __all__
if ZerodhaStreamer:
    __all__.append('ZerodhaStreamer')
if OfflineStreamer:
    __all__.append('OfflineStreamer')
