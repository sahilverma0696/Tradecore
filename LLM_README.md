# LLM_README - Algorithmic Trading System Architecture

## 🚨 CRITICAL GUIDELINES FOR LLM AGENTS

**ALWAYS READ THIS ENTIRE DOCUMENT BEFORE MAKING ANY CHANGES**

This system follows strict architectural patterns. Violating these patterns will break the system. Follow these rules:

1. **NEVER** create new event types without updating the event bus imports
2. **ALWAYS** use the EventBus for inter-component communication 
3. **NEVER** use direct callbacks or handler registration between components
4. **ALWAYS** inherit from Publisher/Subscriber mixins for event communication
5. **NEVER** import from the wrong candle maker location
6. **ALWAYS** check existing tests before implementing new features
7. **NEVER** modify core architecture without understanding the entire flow

---

## Project Overview

This is a **production-grade algorithmic trading system** implementing VWAP (Volume Weighted Average Price) strategies for Indian markets (NSE F&O) using Zerodha Kite APIs. The system is built on an **event-driven architecture** with strict separation of concerns.

### Core Philosophy
- **Event-Driven**: All communication via EventBus singleton
- **Decoupled Components**: No direct dependencies between modules
- **Publisher-Subscriber Pattern**: Components publish/subscribe to typed events
- **Thread-Safe**: Concurrent access handled properly
- **Testable**: Each component tested in isolation

---

## 🏗️ SYSTEM ARCHITECTURE

### Event Bus Foundation

The **EventBus** is the backbone of the system. ALL components communicate through typed events.

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamers     │───▶│   EventBus      │◀───│  CandleMaker    │
│  (Publishers)   │    │   (Singleton)   │    │ (Pub/Sub)       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Strategies    │◀───│   All Events    │───▶│ Order Manager   │
│  (Subscribers)  │    │   Flow Here     │    │ (Subscriber)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Component Hierarchy & Base Classes

#### 1. **Event System** (`src/core/event_bus/`)
```python
# Base Event Class - ALL events inherit from this
@dataclass
class Event(ABC):
    timestamp: datetime
    source: str

# Publisher Mixin - Components that SEND events
class Publisher:
    def publish_event(self, event: Event)

# Subscriber Mixin - Components that RECEIVE events  
class Subscriber:
    def subscribe_to_event(self, event_type: Type[Event], callback)
```

#### 2. **Core Event Types** (STRICT - Do not modify without updating imports)
```python
# Market Data Events
QuoteReceived     # Raw market quotes from streamers
CandleGenerated   # 5-minute OHLCV + VWAP candles

# Trading Signal Events  
EntrySignal       # Strategy entry decisions
ExitSignal        # Exit condition triggers

# Execution Events
OrderExecuted     # Successful order placement
PositionUpdate    # Position status changes
```

---

## 📁 DIRECTORY STRUCTURE (STRICT LOCATIONS)

```
src/
├── main.py                          # 🎯 ENTRY POINT - EventBus wiring
├── config_manager.py                # Hot-reload JSON config
├── logger_factory.py               # Centralized logging
│
├── core/
│   ├── event_bus/                   # 🚨 CORE ARCHITECTURE
│   │   ├── __init__.py             # Event exports (UPDATE when adding events)
│   │   ├── event_bus.py            # EventBus singleton (NEVER modify lightly)
│   │   ├── events.py               # All event definitions
│   │   └── mixins.py               # Publisher/Subscriber mixins
│   │
│   ├── candle_maker.py             # 🎯 USE THIS ONE (not subdirectory)
│   ├── order_manager.py            # Manages active orders
│   ├── order_object.py             # Order state encapsulation
│   ├── order_logger.py             # CSV order logging
│   └── executioner.py              # Order placement (Kite/Paper)
│
├── market/
│   ├── zerodha/
│   │   ├── zerodha_streamer.py     # Live tick streaming
│   │   └── quote_database.py       # SQLite tick persistence
│   └── binance/
│       └── binance_streamer.py     # Crypto streaming
│
├── strategies/
│   ├── vwap_strategy.py            # 🎯 MAIN TRADING LOGIC
│   └── exit_manager.py             # Exit condition handling
│
└── cli/
    ├── dashboard.py                # Real-time monitoring
    ├── cli_main.py                 # CLI entry point
    └── demo_data.py                # Testing data generator

tests/
├── test_event_bus.py               # 🧪 EventBus comprehensive tests
├── test_candle_maker.py            # CandleMaker event integration
└── test_vwap_flow.py               # End-to-end workflow tests

trading_config.json                 # 🔧 MAIN CONFIGURATION
```

---

## 🔄 EVENT FLOW ARCHITECTURE

### 1. **Market Data Flow**
```
Zerodha/Binance Streamer (Publisher)
    │ publishes QuoteReceived
    ▼
EventBus
    │ routes to subscribers
    ▼  
CandleMaker (Publisher + Subscriber)
    │ subscribes to QuoteReceived
    │ aggregates 5-min candles
    │ publishes CandleGenerated
    ▼
VwapStrategy (Subscriber)
    │ subscribes to CandleGenerated
    │ analyzes VWAP crossovers
```

### 2. **Trading Signal Flow**
```
VwapStrategy (Publisher)
    │ publishes EntrySignal/ExitSignal
    ▼
EventBus
    │ routes to order management
    ▼
OrderManager (Subscriber)
    │ subscribes to Entry/Exit signals
    │ manages order lifecycle
    │ calls Executioner for order placement
```

### 3. **Monitoring Flow**
```
All Components (Publishers)
    │ publish various events
    ▼
EventBus
    │ routes to dashboard
    ▼
CLI Dashboard (Subscriber)
    │ subscribes to ALL event types
    │ real-time display updates
```

---

## 🚨 CRITICAL IMPLEMENTATION RULES

### Rule 1: Event Bus Communication ONLY
```python
# ✅ CORRECT - Use EventBus
class MyComponent(Publisher, Subscriber):
    def __init__(self):
        super().__init__()
        self.subscribe_to_event(QuoteReceived, self.handle_quote)
    
    def handle_quote(self, event: QuoteReceived):
        # Process quote
        new_event = SomeEvent(...)
        self.publish_event(new_event)

# ❌ WRONG - Direct callbacks
class BadComponent:
    def register_handler(self, callback):  # DON'T DO THIS
        self._handlers.append(callback)
```

### Rule 2: Correct Imports (ABSOLUTE PATHS)
```python
# ✅ CORRECT
from src.core.event_bus import EventBus, QuoteReceived, CandleGenerated
from src.core.candle_maker import CandleMaker  # Main one, not subdirectory

# ❌ WRONG  
from src.core.candle.candle_maker import CandleMaker  # Old location
```

### Rule 3: Event Type Definitions
```python
# ✅ CORRECT - Add to events.py
@dataclass
class NewTradingEvent(Event):
    symbol: str
    data: Dict[str, Any]

# Then update __init__.py exports
from .events import (..., NewTradingEvent)
__all__ = [..., 'NewTradingEvent']
```

### Rule 4: Component Inheritance Pattern
```python
# ✅ CORRECT - Trading components inherit mixins
class TradingComponent(Publisher, Subscriber):
    def __init__(self):
        super().__init__()  # CRITICAL - Initialize both mixins
        # Subscribe to relevant events
        self.subscribe_to_event(EventType, self.handler)
```

---

## 🧪 TESTING ARCHITECTURE

### Test Structure
```
tests/
├── test_event_bus.py          # Core EventBus functionality
│   ├── Singleton pattern
│   ├── Pub-sub mechanics  
│   ├── Thread safety
│   ├── Error handling
│   ├── Event history
│   └── Publisher/Subscriber mixins
│
├── test_candle_maker.py       # CandleMaker with EventBus
└── test_vwap_flow.py          # End-to-end workflow
```

### Test Patterns
```python
# EventBus test pattern
def setUp(self):
    EventBus._instance = None  # Reset singleton
    self.event_bus = EventBus()

def tearDown(self):
    EventBus._instance = None  # Clean up

# Event flow test pattern
def test_workflow(self):
    received_events = []
    self.event_bus.subscribe(EventType, lambda e: received_events.append(e))
    
    # Trigger event
    component.do_something()
    
    # Verify event received
    self.assertEqual(len(received_events), 1)
```

---

## 🔧 CONFIGURATION SYSTEM

### trading_config.json Structure
```json
{
  "symbols": ["256265"],           // Instrument tokens
  "name_symbol": "NIFTY",         // Display name
  "api_key": "...",               // Kite credentials
  "paper_trade": true,            // Safe mode
  "default_quantity": 75,         // Order size
  "exit_steps": [[0.01, 0.33]],  // Profit taking steps
  "execution": {                  // Order execution settings
    "quantities": {"default": 75},
    "max_retries": 3
  }
}
```

---

## 🖥️ CLI DASHBOARD SYSTEM

### Real-time Event Monitoring
```python
# Dashboard subscribes to ALL events
class TradingDashboard(Subscriber):
    def __init__(self):
        super().__init__()
        self.subscribe_to_event(QuoteReceived, self.update_quotes)
        self.subscribe_to_event(EntrySignal, self.update_signals)
        # ... all event types

# Usage
python3 -m src.cli.cli_main          # Live dashboard
python3 -m src.cli.cli_main --demo   # Demo mode
```

---

## 🚀 COMMANDS & USAGE

### Development Commands
```bash
# Main trading system
python3 -m src.main

# CLI monitoring (separate terminal)
python3 -m src.cli.cli_main

# Run all tests
python3 -m unittest discover -s tests

# Specific test files
python3 -m unittest tests.test_event_bus
python3 -m unittest tests.test_candle_maker
```

### Testing Commands
```bash
# Event bus tests (comprehensive)
python3 -m unittest tests.test_event_bus.TestEventBus.test_singleton_pattern
python3 -m unittest tests.test_event_bus.TestEventBus.test_thread_safety

# Integration tests
python3 -m unittest tests.test_vwap_flow
```

---

## 🔄 EXTENDING THE SYSTEM

### Adding New Event Types
1. **Define in events.py**
```python
@dataclass  
class NewEvent(Event):
    field1: str
    field2: int
```

2. **Update __init__.py exports**
```python
from .events import (..., NewEvent)
__all__ = [..., 'NewEvent']
```

3. **Create publisher**
```python
class EventPublisher(Publisher):
    def trigger_event(self):
        event = NewEvent(field1="test", field2=42, 
                        timestamp=datetime.now(), source=self.__class__.__name__)
        self.publish_event(event)
```

4. **Create subscriber**
```python
class EventSubscriber(Subscriber):
    def __init__(self):
        super().__init__()
        self.subscribe_to_event(NewEvent, self.handle_new_event)
```

### Adding New Components
1. **Inherit from mixins**
```python
class NewTradingComponent(Publisher, Subscriber):
    def __init__(self):
        super().__init__()  # CRITICAL
```

2. **Subscribe to relevant events**
3. **Publish appropriate events**
4. **Add tests**

---

## ⚠️ COMMON PITFALLS FOR LLM AGENTS

### 1. **Wrong CandleMaker Import**
```python
# ❌ WRONG - Old subdirectory structure
from src.core.candle.candle_maker import CandleMaker

# ✅ CORRECT - Main candle maker
from src.core.candle_maker import CandleMaker
```

### 2. **Direct Callback Usage**
```python
# ❌ WRONG - Old callback pattern
component.register_handler(self.handle_data)

# ✅ CORRECT - EventBus pattern
self.subscribe_to_event(EventType, self.handle_data)
```

### 3. **Missing Mixin Initialization**
```python
# ❌ WRONG - Breaks event system
class Component(Publisher):
    def __init__(self):
        pass  # Missing super().__init__()

# ✅ CORRECT
class Component(Publisher):
    def __init__(self):
        super().__init__()  # CRITICAL
```

### 4. **Event Type Confusion**
```python
# ❌ WRONG - Using wrong event types
from src.core.streamer.events import QuoteEvent  # Doesn't exist

# ✅ CORRECT - Use defined events
from src.core.event_bus import QuoteReceived, CandleGenerated
```

---

## 🎯 QUICK REFERENCE FOR LLM AGENTS

### Before Making ANY Changes:
1. ✅ Check which components exist and their inheritance
2. ✅ Verify correct import paths
3. ✅ Understand event flow for the feature
4. ✅ Check existing tests for patterns
5. ✅ Ensure EventBus singleton is properly handled

### When Adding Features:
1. 🎯 Define events first
2. 🎯 Update exports in __init__.py
3. 🎯 Implement Publisher/Subscriber components
4. 🎯 Add comprehensive tests
5. 🎯 Update this README if architecture changes

### Testing Requirements:
- ✅ Event bus singleton reset in setUp/tearDown
- ✅ Event flow verification
- ✅ Thread safety for concurrent features
- ✅ Error handling in event subscribers

---

## 📋 SYSTEM STATUS & CAPABILITIES

### ✅ Implemented & Tested
- Event-driven architecture with EventBus singleton
- Publisher/Subscriber mixins for components
- Comprehensive event bus tests (singleton, thread-safety, error handling)
- Market data streaming (Zerodha/Binance)
- VWAP candle generation with event publishing
- Trading strategy with entry/exit signals
- Order management with event subscription
- Real-time CLI dashboard
- Configuration hot-reloading

### 🔄 Current Event Types
- QuoteReceived (market data)
- CandleGenerated (OHLCV + VWAP)
- EntrySignal (strategy decisions)  
- ExitSignal (exit conditions)
- OrderExecuted (order placement)
- PositionUpdate (position tracking)

### 🎯 Architecture Strengths
- **Decoupled**: Components communicate only via events
- **Testable**: Each component tests in isolation
- **Extensible**: New events/components easy to add
- **Thread-safe**: Concurrent access properly handled
- **Observable**: All system activity flows through EventBus

---

**🚨 REMEMBER: This system's power comes from strict adherence to the event-driven architecture. Breaking these patterns will break the system. When in doubt, follow the existing patterns and test thoroughly.**
