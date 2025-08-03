from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from abc import ABC


@dataclass
class Event(ABC):
    """Base event class for all events in the system."""
    timestamp: datetime
    source: str
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


@dataclass
class QuoteReceived(Event):
    """Event fired when a new market quote is received."""
    symbol: str
    instrument: int
    ltp: float
    volume: int
    last_quantity: int
    change: float
    raw_data: Dict[str, Any]


@dataclass
class CandleGenerated(Event):
    """Event fired when a new candle is completed."""
    symbol: str
    candle_data: Dict[str, Any]
    timeframe: str = "5m"


@dataclass
class EntrySignal(Event):
    """Event fired when strategy generates an entry signal."""
    symbol: str
    side: str  # 'BUY' or 'SELL'
    entry_price: float
    entry_vwap: float
    quantity: int
    exit_steps: list
    strategy_name: str
    candle_data: Dict[str, Any]


@dataclass
class ExitSignal(Event):
    """Event fired when exit conditions are met."""
    symbol: str
    exit_price: float
    exit_reason: str
    quantity: int
    order_id: Optional[str] = None


@dataclass
class OrderExecuted(Event):
    """Event fired when an order is executed."""
    symbol: str
    side: str
    price: float
    quantity: int
    order_id: str
    execution_type: str  # 'ENTRY' or 'EXIT'


@dataclass
class PositionUpdate(Event):
    """Event fired when position is updated."""
    symbol: str
    position_size: int
    avg_price: float
    unrealized_pnl: float
    realized_pnl: float


@dataclass
class MarketDataUpdate(Event):
    """Event fired for general market data updates."""
    symbol: str
    data_type: str
    data: Dict[str, Any]
