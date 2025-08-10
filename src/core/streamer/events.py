from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from src.core.event_bus.events import Event


@dataclass
class QuoteEvent(Event):
    """Standardized quote event for all market data sources."""
    symbol: str
    instrument_token: str  # Can be string or number based on exchange
    ltp: float  # Last Traded Price
    ltq: int    # Last Traded Quantity
    volume: int
    change: float
    change_percent: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_quantity: Optional[int] = None
    ask_quantity: Optional[int] = None
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    previous_close: Optional[float] = None
    exchange: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        super().__post_init__()
        # Ensure required fields are valid
        if self.ltp <= 0:
            raise ValueError(f"Invalid LTP: {self.ltp}")
        if self.ltq < 0:
            raise ValueError(f"Invalid LTQ: {self.ltq}")
        if self.volume < 0:
            raise ValueError(f"Invalid volume: {self.volume}")
